---
title: 时间与数据包装类型
library: tm_infra
headers: [tm_kit/infra/WithTimeData.hpp, tm_kit/infra/ChronoUtils.hpp, tm_kit/infra/VersionedData.hpp, tm_kit/infra/TupleVariantHelper.hpp]
keywords: [WithTime, TimedDataWithEnvironment, TimedAppData, TimedAppModelKleisli, TimedAppMultiData, TimedAppModelContinuation, Key, KeyedData, IsKey, IsKeyedData, VersionChecker, VersionedData, GroupedVersionedData, finalFlag, final flag, ChronoUtils, 时区, zoned_time, C++20, 时间戳, withtime_utils, parseLocalTodayActualTime, keyify, resolveTime, TimeChecker, CheckTimeComponent, 时间倒流, TupleVariantHelper]
---

# 时间与数据包装类型

## 用途

图中节点之间流动的不是裸业务对象，而是**带时间戳和 final 标记的数据包**。这个包装层是 TM Kit 能让同一套业务代码在实时与回测模式下行为一致的关键：时间从环境来而不是从 `std::chrono::system_clock::now()` 来，时序检查由框架统一做。

本篇讲这些包装类型本身（`WithTime`、`TimedDataWithEnvironment` 及其别名族）、key/tag 类型（`Key`、`KeyedData`）、版本倒退丢弃机制（`VersionChecker`）、时间工具函数（`withtime_utils`），以及时序检查在两种模式下的差异。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/WithTimeData.hpp>     // WithTime / TimedDataWithEnvironment / Key / KeyedData
#include <tm_kit/infra/ChronoUtils.hpp>      // 时间解析与格式化
#include <tm_kit/infra/VersionedData.hpp>    // VersionedData / VersionChecker
#include <tm_kit/infra/TupleVariantHelper.hpp>
```

类型在 `dev::cd606::tm::infra`，工具函数在 `dev::cd606::tm::infra::withtime_utils`。

## 核心类型与签名

### WithTime<T, TimePoint>

`tm_infra/tm_kit/infra/WithTimeData.hpp:276`：

```cpp
template <class T, class TimePoint = int64_t>
struct WithTime {
    using TimePointType = TimePoint;
    using ValueType = T;
    TimePoint timePoint;
    T value;
    bool finalFlag;

    template <class F> auto map(F const &f) const -> WithTime<decltype(f(this->value))>;
    template <class A, class F> static WithTime apply(F const &f, WithTime<A, TimePoint> const &x);
    template <class A, class F> static WithTime apply(F const &f, WithTime<A, TimePoint> &&x);
};
```

三要素：`timePoint`（事件时间）、`value`（业务数据）、`finalFlag`（是否为本流最后一个数据）。

裸指针被显式禁止：`template <class T, class TimePoint> struct WithTime<T *, TimePoint> {};`（`WithTimeData.hpp:298`），特化为空结构体，用了就编译不过。原因是框架需要对数据做拷贝（`clone`），裸指针的拷贝语义无法保证。`std::unique_ptr<T>` 是允许的，且有专门的拷贝器与 `operator<<`（`:311`、`:433`）。

### TimedDataWithEnvironment<T, Env, TimePoint>

`WithTimeData.hpp:446` —— 这才是节点间真正流动的数据包：

```cpp
template <class T, class Environment, class TimePoint=typename Environment::TimePointType>
struct TimedDataWithEnvironment {
    using ValueType = T;
    Environment * const environment;
    WithTime<T, TimePoint> timedData;
    // ...
    TimedDataWithEnvironment clone() const;                                    // :468
    template <class F> auto map(F const &f, bool preserveTime=false) const;    // :474
    template <class F> auto mapMove(F const &f, bool preserveTime=false) &&;   // :485
    TimedDataWithEnvironment &overrideTime(TimePoint const &tp);               // :496
    TimedDataWithEnvironment &overrideTime();                                  // :500
    auto moveToAny() && -> TimedDataWithEnvironment<std::any, Environment, TimePoint>; // :504
};
```

每个数据包都带着 `environment` 裸指针，所以业务函数在 kleisli 形态下可以直接 `x.environment->log(...)` 或 `x.environment->now()`，无需额外捕获。`environment` 是 `const` 成员，因此这个类型**可移动、可拷贝赋值（只赋 `timedData`），但不能换环境**。

`map` / `mapMove` 的 `preserveTime` 参数决定输出时间戳：`false`（默认）时调 `environment->resolveTime(timedData.timePoint)` 重新解析，`true` 时沿用输入时间。这个开关是实时/回测差异的落点，下文详述。

### 别名族

`WithTimeData.hpp:443`、`:549`–`:563`：

| 别名 | 定义 | 使用场合 |
|---|---|---|
| `OptionalWithTime<T,TimePoint>` | `std::optional<WithTime<T,TimePoint>>`（`:443`） | 不带环境的可选数据 |
| `TimedAppData<T,Env,TimePoint>` | `std::optional<TimedDataWithEnvironment<...>>`（`:549`） | **节点输出的通用形态**：`nullopt` 表示本次不产出 |
| `TimedAppModelKleisli<A,B,Env,TimePoint>` | `std::function<TimedAppData<B,...>(TimedDataWithEnvironment<A,...> &&)>`（`:552`） | kleisli 函数签名：收完整数据包、返回可选数据包 |
| `TimedAppMultiData<T,Env,TimePoint>` | `std::optional<TimedDataWithEnvironment<std::vector<T>,...>>`（`:555`） | multi 形态节点的输出：一次产出多个值，共享同一时间戳 |
| `TimedAppModelContinuation<A,B,ContinuationStructure,Env,TimePoint>` | 见 `:558`–`:564` | 延续式（continuation）形态，用于 facility 这类"一个输入对多个异步输出" |

`TimedAppModelContinuation` 的完整签名：

```cpp
// WithTimeData.hpp:558
template <class A, class B, class ContinuationStructure, class Environment, class TimePoint=typename Environment::TimePointType>
using TimedAppModelContinuation = std::function<
    void(
        TimedDataWithEnvironment<A, Environment, TimePoint> &&
        , ContinuationStructure &
        , std::function<void(TimedDataWithEnvironment<B, Environment, TimePoint> &&)>
    )
>;
```

各 App 类型把这些别名重新暴露为 `M::Data<T>`、`M::InnerData<T>` 等更短的名字，日常写业务用后者——见 [01-app-types.md](01-app-types.md)。

### Key<T,Env> 与 KeyedData<K,D,Env>

`WithTimeData.hpp:79` 与 `:150`。这是 facility 的请求/响应配对机制的类型基础；facility 侧的用法见 [04-facilities.md](04-facilities.md)，这里只讲类型层面。

```cpp
// WithTimeData.hpp:79
template <class T, class Env>
class Key {
private:
    typename Env::IDType id_;
    T key_;
public:
    using KeyType = T;
    Key();                                  // :85
    Key(typename Env::IDType u, T const &k);
    Key(T const &k);                        // :88 —— 自动调 Env::new_id()
    typename Env::IDType id() const;        // :95
    T const &key() const;                   // :98
    bool operator==(Key<T,Env> const &k) const;   // :104
    bool operator<(Key<T,Env> const &k) const;    // :112
    template <class F> auto map(F const &f) const -> Key<decltype(f(this->key_)), Env>;  // :119
};
```

ID 由 Environment 的 ID component 生成（`Env::new_id()`），所以 `Key` 的唯一性与 Environment 绑定。三个禁止性特化（全部为空结构体）：

```cpp
template <class T, class Env> class Key<T *, Env> {};              // :126 不允许裸指针做 key
template <class T, class Env> class Key<std::unique_ptr<T>, Env> {}; // :128 不允许 unique_ptr 做 key
template <class T, class Env> class Key<Key<T,Env>, Env> {};        // :130 不允许嵌套 Key
```

```cpp
// WithTimeData.hpp:150
template <class K, class D, class Env>
struct KeyedData {
    using KeyType = K;
    using DataType = D;
    Key<K,Env> key;
    D data;
    template <class F> static KeyedData map(F const &f, Key<K,Env> const &k);
};
```

`KeyedData` 把请求（`key`，含 ID 与原始请求内容）与响应（`data`）绑在一起回传，调用方因此能把响应匹配回请求。

配套 trait：

| trait | 位置 | 说明 |
|---|---|---|
| `IsKey<T>` | `:133`（false 基础）、`:137`（`Key<T,Env>` 为 true） | 另有 `is_key_v`（`:141`） |
| `IsKeyedData<T>` | `:162`、`:166`，并对 `std::variant<A,OtherAs...>` 递归（`:176`） | 另有 `is_keyed_data_v`（`:180`） |
| `IsMonoStateKeyedData<T>` | `:183`、`:187`（`KeyedData<std::monostate,B,Env>` 为 true） | 另有 `is_monostate_keyed_data_v`（`:190`） |

`IsKeyedData` 对 variant 递归（任一分支是 `KeyedData` 即为真）这一点很重要：`AppRunner` 注册节点时用它判断是否要把节点登记进 `typedKeyedDataSinks_`（见 `WithTimeData.hpp:1162`、`:1230`），`NodeClassifier` 也用 `is_monostate_keyed_data_v` 区分 facility 族（`tm_infra/tm_kit/infra/NodeClassifier.hpp:325`）。

`Key` 与 `KeyedData` 都有 `operator<<`（`:181`、`:193`），打印形如 `{id=...,key=...}`。

### VersionChecker 与 VersionedData

`tm_infra/tm_kit/infra/VersionedData.hpp` 定义带版本号的数据与"丢弃版本倒退"的检查器。

```cpp
// VersionedData.hpp:25（有 enable_if 约束 VersionType 可拷贝可默认构造）
template <class VersionType, class DataType, class CmpType>
struct VersionedData<...> {
    using Version = VersionType; using Data = DataType; using Cmp = CmpType;
    VersionType version;
    DataType data;
};

// VersionedData.hpp:52
template <class GroupIDType, class VersionType, class DataType, class CmpType>
struct GroupedVersionedData<...> {
    GroupIDType groupID;
    VersionType version;
    DataType data;
};
```

`CmpType` 默认 `std::less<VersionType>`（`VersionedData.hpp:15`、`:40`），所以"更新"的定义是版本号更大；要实现别的顺序（如倒序版本号）换掉 `CmpType` 即可。

#### 现成的 CmpType 实现（`VersionedData.hpp:204`–`:280`）

当版本号本身是个**数组或 map**（例如"每个字段各有一个版本号"的数据模型），默认的 `std::less` 不适用。`VersionedData.hpp` 提供了四个比较器：

| 比较器 | 行号 | 语义 |
|---|---|---|
| `FullArrayComparer<T,N>` | `:204` | 逐元素比较 `std::array<T,N>`，全部不降且至少一个上升才算"更新" |
| `ArrayComparerWithSkip<T,N>` | `:219` | 同上，但**跳过等于默认值 `T{}` 的元素**——用于"该字段本次未更新"用零值表示的场景 |
| `ArrayComparerWithOptional<T,N>` | `:238` | 元素类型是 `std::optional<T>`，跳过 `nullopt` 的元素 |
| `MapComparerWithSkip<Key,T,KeyCmp>` | `:257` | map 版本，跳过值为默认值的键。**只接受 `std::map` 不接受 `unordered_map`**（源码注释 `:254`：需要 key 有序才能做线性归并比较） |

`ArrayComparerWithSkip` 的核心逻辑（`:219`）：

```cpp
// VersionedData.hpp:219-235（节选）
template <class T, std::size_t N>
struct ArrayComparerWithSkip {
    bool operator()(std::array<T,N> const &a, std::array<T,N> const &b) const {
        static const T defaultVal {};
        for (size_t ii=0; ii<N; ++ii) {
            if (a[ii] == defaultVal || b[ii] == defaultVal) {
                continue;              // ← 默认值表示"该分量未更新"，跳过
            }
            if (a[ii] < b[ii]) { return true; }
            if (a[ii] > b[ii]) { return false; }
        }
        return false;
    }
};
```

**这组比较器的意义**：向量版本号是"部分更新"的建模方式——一次更新只改动若干字段，其余字段留默认值表示"不变"。用 `std::less` 比较整个数组会把"未更新"误判为"版本倒退"，导致数据被 `VersionChecker` 静默丢弃。选比较器前先确认你的版本号是标量还是向量、以及"未更新"用什么表示。

`VersionChecker<T>` 的基础模板直接放行一切（`VersionedData.hpp:71`–`:76`，`checkVersion` 是静态函数恒返回 `true`），只有特化版本真的检查：

| 特化 | 位置 | 状态 |
|---|---|---|
| `VersionChecker<VersionedData<V,D,Cmp>>` | `:78` | 单个 `std::optional<VersionType> lastVersion_` |
| `VersionChecker<GroupedVersionedData<G,V,D,Cmp>>` | `:96` | `unordered_map<GroupIDType, VersionType>`，按 group 分别记 |
| `VersionChecker<VersionedData<V,std::optional<D>,Cmp>>` | `:118` | 同上，data 可为空 |
| `VersionChecker<GroupedVersionedData<G,V,std::optional<D>,Cmp>>` | `:140` | 同上 |
| `VersionChecker<std::unique_ptr<A>>` / `<std::shared_ptr<A>>` | `:166` / `:179` | 转发给 `VersionChecker<std::decay_t<A>>` |
| `VersionChecker<std::tuple<A,B>>` | `:192` | 两个子检查器，都通过才算通过 |

单版本的检查逻辑（`:86`–`:94`）：

```cpp
bool checkVersion(VersionedData<VersionType,DataType,CmpType> const &t) {
    if (!lastVersion_ || cmp_(*lastVersion_, t.version)) {
        lastVersion_ = t.version;
        return true;
    } else {
        return false;
    }
}
```

返回 `false` 意味着**这条数据被丢弃**。

`WithTimeData.hpp` 里还有两个针对 `KeyedData` 的特化：

```cpp
// WithTimeData.hpp:229
template <class A, class VersionType, class DataType, class Env, class CmpType>
class VersionChecker<KeyedData<A,VersionedData<VersionType,DataType,CmpType>,Env>>;
// WithTimeData.hpp:247
template <class A, class GroupIDType, class VersionType, class DataType, class Env, class CmpType>
class VersionChecker<KeyedData<A,GroupedVersionedData<GroupIDType,VersionType,DataType,CmpType>,Env>>;
```

它们内部是 `unordered_map<Env::IDType, VersionChecker<...>>`——**按请求 ID 分别记版本**。注释（`WithTimeData.hpp:226`–`:227`）说明了为什么：`Key` 本身一个 ID 只用一次，无需检查版本；但 `KeyedData` 作为订阅响应会对同一个 ID 反复推送，必须按 ID 分别检查。

这就是订阅式行情/状态同步的核心保护：一个订阅请求对应一个 ID，服务端陆续推送带版本的状态更新，网络乱序或重连重放导致的旧版本数据会被自动丢掉。`tm_basic` 的 transaction 模块大量依赖它（`tm_basic/tm_kit/basic/transaction/v2/DataStreamInterface.hpp` 等）。

辅助函数 `updateVersionedData`（`VersionedData.hpp:311`、`:319`）用同一套比较逻辑原地更新一份 `VersionedData`。

### finalFlag 的语义

`WithTimeData.hpp:267`–`:275` 的注释是关于 `finalFlag` 最权威的说明，要点：

- **含义**：发送方（action 或 importer）此后永不再发；若是 facility，则对本请求永不再回。
- `BasicWithTimeApp`：忽略。
- `RealTimeApp`：用它来"摘掉"（unhook）facility——某个请求收到 final 响应后，这个请求的回调被清理；除此之外不太用。
- `SinglePassIterationApp`：**重度依赖**。下游组件看到 final 标记才停止继续拉数据；**如果某个 action 永远不发 final 标记，下游就永远拉不完，整个执行不会结束**。

这是回测程序"跑完不退出"最常见的原因。回测的收尾一般靠一个显式的退出定时器而不是指望自然终止：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:226-235
basic::AppRunnerUtilComponents<R>::setupExitTimer(
    r
    , std::chrono::hours(24)
    , dataInput.clone()
    , [](TheEnvironment *env) { env->log(infra::LogLevel::Info, "Wrapping up!"); }
    , "exitTimerPart"
);
```

对应地，回测用的 Environment 要带 `infra::FlagExitControlComponent`（`MainLogic.cpp:193`）而不是 `TrivialExitControlComponent`，否则退出请求没人响应。

### withtime_utils 工具函数

`WithTimeData.hpp` 里 `withtime_utils` 命名空间分四段出现（`:199`、`:326`、`:513`、`:566`、`:589`）：

拷贝族（`:326` 起）：

| 名字 | 位置 | 说明 |
|---|---|---|
| `ValueCopier<A>::copy` | `:328` | 通用值拷贝；对 `unique_ptr`（`:336`）、`tuple`（`:346`）、`variant`（`:365`）、`Key`（`:389`）、`KeyedData`（`:395`）、`VersionedData`（`:401`）、`GroupedVersionedData`（`:410`）有特化 |
| `makeValueCopy(A const &)` | `:421` | `ValueCopier` 的函数门面 |
| `makeCopy(WithTime<A,TimePoint> const &)` | `:426`、`:433` | 整个数据包的深拷贝 |
| `clone(TimedAppData<...> const &)` | `:568` | 对可选数据包做深拷贝 |

key 族（`:199` 起）：

| 名字 | 位置 | 说明 |
|---|---|---|
| `keyify<A,Env>(A &&a)` | `:201` | 包成 `Key<A,Env>`，自动分配 ID |
| `apply(F const &f, Key<A,Env> ...)` | `:205`、`:209` | 保持 ID 不变、变换 key 内容 |
| `keyedDataFromKey(F const &f, Key<A,Env> ...)` | `:213`、`:217` | 用 key 算出 data，组成 `KeyedData` |
| `discardInputPartFromKeyedData(KeyedData<A,B,Env> &&)` | `:221` | 丢掉请求部分，只留 `Key<B,Env>` |

`keyify` 在组图时常被直接当作 lift 的函数对象：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:93
auto keyify = M::template liftPure<simple_demo::CalculateCommand>(
    dev::cd606::tm::infra::withtime_utils::keyify<simple_demo::CalculateCommand, typename M::EnvironmentType>
);
```

也可以在声明式组图里直接用：

```cpp
// 来源：tm_examples/clock_logic_test/ClockLogicMain.hpp:89
, {"converter", infra::withtime_utils::keyify<std::string, typename M::EnvironmentType>}
```

构造族（`:513` 起）：

| 名字 | 位置 | 说明 |
|---|---|---|
| `pureTimedDataWithEnvironment(Env*, T &&t, bool finalFlag=false)` | `:515` | 用 `env->resolveTime()` 现取时间，包成数据包 |
| `pureTimedDataWithEnvironment(Env*, WithTime<T,TimePoint> &&, bool preserveTime=false)` | `:520` | 从已有 `WithTime` 构造 |
| `pureTimedDataWithEnvironment(TimedDataWithEnvironment<A,...> &&, bool preserveTime=false)` | `:524` | 重新解析时间（或不解析） |
| `pureTimedDataWithEnvironmentLift(...)` | `:532`、`:536`、`:540`、`:544` | 四个重载：`F` 按引用/按 const 引用 × 从 `WithTime` / 从 `TimedDataWithEnvironment`。作用是"套一层函数再包成数据包"，是 `liftPure` 的实现基石 |
| `timedAppApply(TimedAppModelKleisli<A,B,...> const &f, TimedAppData<A,...> &&)` | `:579` | 对可选数据包应用 kleisli 函数，输入为空则直接返回 `nullopt` |

类型萃取族（`:589` 起）：`ActionTypeInfo`、`ImporterTypeInfo`、`ExporterTypeInfo`、`OnOrderFacilityTypeInfo`、`VIEOnOrderFacilityTypeInfo`（`:590`–`:614`），以及 `IsVariant<T>`（`:617`、`:622`）。`AppRunner` 的所有 `register*` / `*AsSource` / `*AsSink` 都靠它们从节点类型反推输入输出类型——见 [05-app-runner.md](05-app-runner.md)。

### ChronoUtils.hpp

`tm_infra/tm_kit/infra/ChronoUtils.hpp`，全部在 `withtime_utils` 下。声明在头文件、实现在 `tm_infra/src/ChronoUtils.cpp` 的一组（`ChronoUtils.hpp:14`–`:24`）：

| 函数 | 头文件行 | 实现行 | 说明 |
|---|---|---|---|
| `parseLocalTime(int year,int month,int day,int hour,int minute,int second,int microseconds=0)` | `:14` | `src/ChronoUtils.cpp:9` | 本地时区分量 → time_point |
| `parseLocalTodayActualTime(int hour,int minute,int second,int microseconds=0)` | `:15` | `src/ChronoUtils.cpp:20` | **今天的某个时刻**（取挂钟当天日期） |
| `parseLocalTime(std::string_view const &s)` | `:17` | `src/ChronoUtils.cpp:29` | 格式固定 `yyyy-MM-ddTHH:mm:ss.mmmmmm`，微秒部分可省 |
| `localTimeString(time_point const &tp)` | `:18` | `src/ChronoUtils.cpp:65` | 反向格式化 |
| `parseUtcTime(int,...)` / `parseUtcTime(string_view)` | `:19` / `:21` | `src/ChronoUtils.cpp:87` / `:103` | UTC 版，字符串格式带尾部 `Z` |
| `parseZonedTime(std::string_view const &s)` | `:23` | `src/ChronoUtils.cpp:146` | 格式 `yyyy-MM-ddTHH:mm:ss.mmmmmm+/-HH:mm` |
| `utcTimeString(time_point const &tp)` | `:24` | `src/ChronoUtils.cpp:177` | UTC 格式化 |

头文件内联的模板工具：

| 函数/类 | 位置 | 说明 |
|---|---|---|
| `genericLocalTimeString<TimeType>(t)` | `:26`，`system_clock::time_point` 特化在 `:32` | 对任意 `TimePointType` 都能打印，非 `system_clock` 的走 `operator<<` |
| `sinceMidnight<Duration>(tp)` | `:38` | 距当日本地午夜的时长计数，用法 `sinceMidnight<std::chrono::seconds>(tp)` |
| `sinceEpoch<Duration>(tp)` | `:49` | 距 epoch 的时长计数，`constexpr` |
| `epochDurationToTime<Duration>(int64_t d)` | `:54` | `sinceEpoch` 的逆运算，`constexpr` |
| `MemorizedMidnight<Env>` | `:68` | 预先算好午夜点并缓存，避免高频调用 `localtime`；成员 `sinceMidnight<Duration>()`（`:86`）、`midnightDurationToTime<Duration>()`（`:90`） |

C++20 时区族，**仅在 `__cplusplus >= 202002L` 且（MSVC 或 GCC ≥ 13）时可用**（`:98` 的条件编译）：`parseZonedTime(分量..., timeZoneName)`（`:102`）、`parseZonedTime(timeString, timeZoneName)`（`:109`）、`parseZonedTodayActualTime(...)`（`:145`）、`zonedTimeString(...)`（`:153`）、`sinceZonedMidnight<Duration>(...)`（`:193`）、`MemorizedZonedMidnight<Env>`（`:208`）。头文件注释（`:97`）说明 gcc 的 `zoned_time` 支持长期不完整，所以这部分不能放进 `.cpp`。

真实用例：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:177-179
infra::terminationController(infra::TerminateAtTimePoint {
    infra::withtime_utils::parseLocalTodayActualTime(23, 59, 59)
});
```

实时程序跑到当天 23:59:59 自动收工。对照回测版（`MainLogic.cpp:258`）用 `ImmediatelyTerminate` ——见 [08-runners-and-control.md](08-runners-and-control.md)。

解析固定时点的用法：

```cpp
// 来源：tm_examples/clock_logic_test/main.cpp:61-65
infra::terminationController(infra::TerminateAtTimePoint {
    env.actualTime(
        infra::withtime_utils::parseLocalTime("2020-01-01T10:01:05")
    )
});
```

注意这里套了一层 `env.actualTime(...)` ——虚拟时钟下逻辑时间与挂钟时间不是一回事，详见 [../tm_basic/01-clocks.md](../tm_basic/01-clocks.md)。

格式化用于日志：

```cpp
// 来源：tm_examples/common_flow_util_tests/DelayTest.cpp:39
x.environment->log(infra::LogLevel::Info, infra::withtime_utils::localTimeString(x.timedData.value));
```

### TupleVariantHelper.hpp

`tm_infra/tm_kit/infra/TupleVariantHelper.hpp`，纯类型层工具，服务于多输入/多输出节点的代码生成：

| 名字 | 位置 | 说明 |
|---|---|---|
| `TupleConcat<A,B>` | `:20` | 把 A 加到 `std::tuple<Bs...>` 前面 |
| `VariantConcat<A,B>` | `:33` | 同上，对 `std::variant` |
| `TupleRepeat<N,T>` | `:46` | `std::tuple<T,T,...>`（N 个） |
| `VariantRepeat<N,T>` | `:60` | `std::variant<T,T,...>`（N 个） |
| `dispatchVariantConstruct<N,T>(std::size_t idx, T &&t)` | `:79` | **运行期**下标 → 构造 `VariantRepeat<N,T>` 的对应分支 |
| `augmentedDispatchVariantConstruct<N,S,T>(idx, T &&t)` | `:98` | 同上，但 variant 前面多一个 S 分支（下标整体 +1） |
| `TupleVariantConversion<T>` | `:116` | `tuple<Ts...>` ↔ `variant<Ts...>` 互转 |

多输入节点把输入建模为 `std::variant`、多输出建模为 `std::tuple`（见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md)），这组工具就是在这两种表示之间做类型层转换。`dispatchVariantConstruct` 解决的是"运行期知道是第几路输入，但 variant 的分支下标必须是编译期常量"这个矛盾。

## 实时 / 回测行为差异

这是本篇最关键的小节。时间的产生与校验在两种模式下走的是不同代码。

### 时间从哪来：resolveTime

`TimedDataWithEnvironment::map` 默认（`preserveTime == false`）调 `environment->resolveTime(timedData.timePoint)`，不同时钟组件的实现完全不同：

| 时钟组件 | `resolveTime()` | `resolveTime(triggeringInputTime)` |
|---|---|---|
| `basic::real_time_clock::ClockComponent` | `Clock::now()`（`tm_basic/tm_kit/basic/real_time_clock/ClockComponent.hpp:26`） | **忽略入参**，仍返回 `Clock::now()`（`:29`） |
| `basic::real_time_clock::SimplifiedClockComponent` | 返回默认构造的时间点（`:53`） | 返回 `triggeringInputTime`（`:56`） |
| `basic::single_pass_iteration_clock::ClockComponent`（亦即 `top_down_single_pass_iteration_clock::ClockComponent`，后者是前者的别名，见 `tm_basic/tm_kit/basic/top_down_single_pass_iteration_clock/ClockComponent.hpp:9`） | `Clock::now()`（`tm_basic/tm_kit/basic/single_pass_iteration_clock/ClockComponent.hpp:17`） | `updateLatestTime(triggeringInputTime)` 后返回 `triggeringInputTime`（`:20`） |

关键差异：**实时模式下输出时间戳是"处理完的挂钟时刻"，单遍迭代模式下输出时间戳是"触发它的输入的时间戳"**。后者还顺手把全局时钟推进到该时刻，这正是回测里"时间由数据驱动"的实现方式。

另外注意 `PreserveInputRelativeOrder`：实时时钟是 `false`（`real_time_clock/ClockComponent.hpp` 的 `ClockComponent`），单遍迭代时钟是 `true`（`single_pass_iteration_clock/ClockComponent.hpp:14`）。

### 时间倒流检查：TimeChecker 与 CheckTimeComponent

`CheckTimeComponent<DoCheck>`（`tm_infra/tm_kit/infra/Environments.hpp:42`）只做一件事：暴露 `static constexpr bool CheckTime = DoCheck;`（`:43`）。各 App 的 `TimeChecker` 读这个常量决定是否丢弃时间倒退的数据。

`RealTimeApp` 的 `TimeChecker` 有两个版本，由 `MutexProtected` 模板参数选择：

```cpp
// tm_infra/tm_kit/infra/RealTimeApp.hpp:58-60
template <bool MutexProtected, class T>
class TimeChecker {};
template <class T>
class TimeChecker<false, T> { /* :61 起，成员 bool hasData_ */ };
```

非保护版（`RealTimeApp.hpp:61`–`:83`）的检查体：

```cpp
// tm_infra/tm_kit/infra/RealTimeApp.hpp:67-78
inline bool operator()(TimedDataWithEnvironment<T, StateT, typename StateT::TimePointType> const &data) {
    if (!versionChecker_.checkVersion(data.timedData.value)) {
        return false;
    }
    if (StateT::CheckTime) {
        if (hasData_ && data.timedData.timePoint < lastTime_) {
            return false;
        }
    }
    hasData_ = true;
    lastTime_ = data.timedData.timePoint;
    return true;
}
```

mutex 保护版（`RealTimeApp.hpp:84`–`:109`）逻辑完全相同，区别是：成员 `hasData_` 是 `std::atomic<bool>`、多一个 `std::mutex mutex_`，`operator()` 开头 `std::lock_guard<std::mutex> _(mutex_);`（`:94`）。**用保护版还是非保护版取决于该节点的输入是否可能被多个线程并发推送**；单线程处理器用非保护版省掉锁开销（例如 `ThreadedHandlerBase` 内部用的是 `TimeChecker<false, T>`，`RealTimeApp.hpp:116`）。

`TopDownSinglePassIterationApp` 只有一个版本（`tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:158`），逻辑与 `RealTimeApp` 的非保护版一字不差——因为单遍迭代是单线程，不需要锁。

两处都先查版本再查时间：**版本检查无条件执行，时间检查受 `StateT::CheckTime` 门控**。所以即使 `CheckTimeComponent<false>`，`VersionChecker` 依然生效。

variant 输入的 `TimeChecker` 由生成文件提供（`tm_infra/tm_kit/infra/RealTimeApp_TimeChecker_Piece.hpp:1` 起、`TopDownSinglePassIterationApp_TimeChecker_Piece.hpp`），**每个分支各记一份 `tp` 和 `versionChecker`**，并用 `std::bitset<N> finalMask_` 分别记录各分支的 final 标记（`RealTimeApp_TimeChecker_Piece.hpp:3`–`:6`、`:24`）——多输入节点要等所有分支都 final 才算整体 final。

### 对照表

| 维度 | RealTimeApp | TopDownSinglePassIterationApp |
|---|---|---|
| 时间戳来源 | 挂钟 `now()`，与输入时间无关 | 触发输入的时间戳，同时推进全局时钟 |
| 典型 `CheckTimeComponent` | `<false>`（`MainLogic.cpp:41`） | `<true>`（`MainLogic.cpp:192`） |
| 时间倒流的数据 | 一般不检查（`CheckTime=false`），直接放过 | 检查并丢弃 |
| `TimeChecker` 版本 | `<false,T>` 与 `<true,T>` 两套，按并发需要选 | 单一版本，无锁 |
| `VersionChecker` | 生效 | 生效 |
| `finalFlag` | 用于摘掉 facility 的请求回调 | 决定下游何时停止拉取，**漏发则永不结束** |
| `PreserveInputRelativeOrder` | `false` | `true` |

`MainLogic.cpp` 两个入口的 Environment 第一行就是这个对照：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40-50（实时，已截取）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::real_time_clock::ClockComponent>,
    ...
>;

// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:191-196（回测）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::FlagExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::top_down_single_pass_iteration_clock::ClockComponent<std::chrono::system_clock::time_point,true>,false>,
    basic::IntIDComponent<>
>;
```

实时模式关掉时间检查是有道理的：挂钟时间下多线程并发产生的时间戳本来就可能微小倒置，一检查就会无谓丢数据。回测模式必须打开：数据按时间顺序喂进来，倒流说明业务逻辑或输入文件有问题。

## 易错点

1. **`finalFlag` 漏发导致回测不结束。** 单遍迭代模式下下游靠它停止拉取。自定义 importer 必须在数据耗尽时发一个带 final 标记的数据包（或走框架提供的 importer 工厂）。表现是程序挂住不退出、CPU 空转。

2. **在业务代码里直接调 `std::chrono::system_clock::now()`。** 这会让回测结果依赖运行时刻，彻底破坏可重放性。一律用 `env->now()` / `env->resolveTime()`，或让框架在 `map` 时自动解析。

3. **`WithTime<T*>` / `Key<T*>` / `Key<std::unique_ptr<T>>` / `Key<Key<T,Env>>` 是空结构体。** 误用时的报错是"没有成员 `value`/`id`"之类，一眼看不出原因是触发了禁止性特化（`WithTimeData.hpp:298`、`:126`、`:128`、`:130`）。

4. **`preserveTime=true` 用错会让时间戳僵住。** `map`/`mapMove` 的这个参数默认 `false`（重新解析时间）。手写 kleisli 时若一路 `preserveTime=true`，回测里全链路会共用最初的时间戳。

5. **`VersionChecker` 的静默丢弃。** 版本检查**不受 `CheckTimeComponent` 控制**，只要数据类型是 `VersionedData` / `GroupedVersionedData`（或含它的 `KeyedData`），版本不前进的数据就被无声丢掉，没有日志。排查"数据明明发了但下游收不到"时要想到这一层。

6. **`GroupedVersionedData` 的版本是按 group 独立的。** `VersionedData.hpp:96` 的实现用 `unordered_map<GroupIDType, VersionType>`，不同 group 之间互不影响。误以为是全局单调会得出错误结论。

7. **`KeyedData` 的 `VersionChecker` 按 ID 分别记。** 一个 ID 的状态推送序列独立于另一个 ID（`WithTimeData.hpp:229`）。所以不同订阅之间版本号不必可比。

8. **C++20 时区函数的可用性。** `parseZonedTime(分量..., zoneName)` 这一族在 GCC < 13 或非 C++20 编译时**不存在**（`ChronoUtils.hpp:98` 的条件编译）。只有不带时区名的 `parseZonedTime(string_view)`（`src/ChronoUtils.cpp:146`）始终可用。

9. **`TimedDataWithEnvironment::environment` 是 `Environment * const`。** 拷贝赋值只赋 `timedData` 不换环境（`WithTimeData.hpp:456`–`:461`）。跨 Environment 传数据包需要显式重建。

## 第三方依赖

- C++ 标准库 `<chrono>`：时间点与时长。C++20 `std::chrono::zoned_time` 用于时区族，参见 [cppreference: zoned_time](https://en.cppreference.com/w/cpp/chrono/zoned_time)。
- 其余为标准库 `<optional>` / `<variant>` / `<tuple>` / `<any>` / `<functional>`，无第三方库依赖（`tm_infra` 的设计目标之一就是零第三方依赖）。

## 相关章节

- [00-overview.md](00-overview.md) —— 框架总览
- [01-app-types.md](01-app-types.md) —— 各 App 对这些类型的再封装（`M::Data<T>` / `M::InnerData<T>`）
- [02-environments.md](02-environments.md) —— `CheckTimeComponent`、ID component、退出控制组件
- [03-nodes-and-lifting.md](03-nodes-and-lifting.md) —— pure / maybe / multi / kleisli / enhanced 各形态如何消费这些类型
- [04-facilities.md](04-facilities.md) —— `Key` / `KeyedData` 在 facility 中的实际用法
- [05-app-runner.md](05-app-runner.md) —— `ActionTypeInfo` 等萃取在注册 API 中的作用
- [08-runners-and-control.md](08-runners-and-control.md) —— `terminationController` 与时间相关的终止策略
- [09-generated-pieces.md](09-generated-pieces.md) —— `*_TimeChecker_Piece.hpp` 等生成文件
- [../tm_basic/01-clocks.md](../tm_basic/01-clocks.md) —— 时钟组件、虚拟时间、`actualTime`
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
