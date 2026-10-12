---
title: on-order facility 四变体
library: tm_infra
headers: [tm_kit/infra/RealTimeApp.hpp, tm_kit/infra/TopDownSinglePassIterationApp.hpp, tm_kit/infra/WithTimeData.hpp, tm_kit/infra/GenericLift.hpp]
keywords: [on-order facility, facility, 按单设施, OnOrderFacility, LocalOnOrderFacility, OnOrderFacilityWithExternalEffects, VIEOnOrderFacility, FacilitioidConnector, FacilityWrapper, Key, KeyedData, keyify, placeOrderWithFacility, liftPureOnOrderFacility, WithStart, wrappedOnOrderFacility, fromAbstractOnOrderFacility, 成环, tag, RPC]
---

# on-order facility 四变体

## 用途

on-order facility（按单设施）是**请求-响应式**节点：接受带 tag 的输入 `Key<A>`，对每个输入产出零个
或多个同 tag 的输出 `KeyedData<A,B>`。它解决两个问题：

1. **让数据流图能成环。** 普通 action 构成的环会被 `AppRunner` 校验拒绝；含 facility 的环只告警。
   "下单 → 收到成交 → 调整下单"这类反馈回路必须靠 facility 实现。
2. **把本地计算与远程 RPC 统一成同一个抽象。** 通过 `FacilitioidConnector`，业务代码不关心响应来自
   本进程的函数还是跨进程的 RabbitMQ 调用——这是量化场景里"实时连真实交易网关、回测连本地模拟器"
   的实现基础。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/RealTimeApp.hpp>
#include <tm_kit/infra/WithTimeData.hpp>   // Key / KeyedData / AppRunner / FacilitioidConnector
#include <tm_kit/infra/GenericLift.hpp>    // GenericLift<M>::liftFacility
```

命名空间：`dev::cd606::tm::infra`。`Key` / `KeyedData` / `withtime_utils::keyify` 在 `infra` 与
`infra::withtime_utils` 下；facility 工厂函数是 app 类型的静态成员；`placeOrderWith*` 与
`facilityConnector` 是 `AppRunner` 的成员。

## 核心类型与签名

### 为什么 facility 能让图成环

`AppRunner::finalize()` 做两轮环检测（`tm_infra/tm_kit/infra/WithTimeData.hpp:2933-2951`）：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:2934-2950（节选）
auto cycleRet = detectCycle(false);
if (cycleRet) {
    throw AppRunnerException("There is a circle starting from '"+(*cycleRet)+"'");
}
cycleRet = detectCycle(true);
if (cycleRet) {
    if constexpr (App::CannotHaveLoopEvenWithFacilities) {
        throw AppRunnerException(... "this monad prohibits this kind of loop too");
    } else {
        env_->log(LogLevel::Warning, "There is a circle involving on-order facility starting from '" + ... + "'");
    }
}
```

`detectCycle(false)` 不把 facility 计入边，发现环即抛异常；`detectCycle(true)` 计入 facility，
发现环只记 Warning。所以规则是：**图中每个环至少要含一个 facility**。

四个 app 类型目前都把 `CannotHaveLoopEvenWithFacilities` 设为 `false`
（`RealTimeApp.hpp:680`、`TopDownSinglePassIterationApp.hpp:94`、`SinglePassIterationApp.hpp:64`、
`BasicWithTimeApp.hpp:21`），因此含 facility 的环在四种模式下都只告警。
`detectCycle` 本身定义在 `WithTimeData.hpp:2798`。

若环确实是刻意设计的，可在 Environment 里加 `infra::graph_check_components::DontCheckCycles`
（`tm_infra/tm_kit/infra/GraphCheckComponents.hpp:9`）跳过检测，真实用例见
`tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:18`。

### Key&lt;T,Env&gt; 与 KeyedData&lt;K,D,Env&gt;

`Key<T,Env>` 定义在 `tm_infra/tm_kit/infra/WithTimeData.hpp:79`，是"值 + 唯一 ID"的配对：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:79-124（节选）
template <class T, class Env>
class Key {
private:
    typename Env::IDType id_;
    T key_;
public:
    using KeyType = T;
    Key(T const &k) : id_(Env::new_id()), key_(k) {}
    Key(typename Env::IDType u, T const &k) : id_(u), key_(k) {}
    typename Env::IDType id() const;
    T const &key() const;
    template <class F>
    auto map(F const &f) const -> Key<decltype(f(this->key_)), Env>;
};
```

单参构造**自动调用 `Env::new_id()`** 生成新 ID；双参构造沿用既有 ID（facility 响应时必须用它来
保持 tag 一致）。`map` 用于在保持 ID 不变的前提下变换载荷，是 facility 包装的基础。

源码显式禁止三类 key（`WithTimeData.hpp:126-130`）：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:125-130
template <class T, class Env>
class Key<T *, Env> {};  //not allowing the holding of a bare pointer as key
template <class T, class Env>
class Key<std::unique_ptr<T>, Env> {};  //not allowing the holding of an unique pointer as key
template <class T, class Env>
class Key<Key<T,Env>, Env> {};  //not allowing duplicate keys
```

这三个特化**故意是空类**，没有任何成员。误用时不会得到"禁止使用"的清晰报错，而是
"没有成员 `key()`"之类的间接错误——见下面的易错点。

`KeyedData<K,D,Env>` 在 `WithTimeData.hpp:150`，是 facility 的输出类型：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:149-159
template <class K, class D, class Env>
struct KeyedData {
    using KeyType = K;
    using DataType = D;
    Key<K,Env> key;
    D data;
    template <class F>
    static KeyedData map(F const &f, Key<K,Env> const &k);
};
```

它同时携带**原始请求**（`key.key()`）与**响应**（`data`），所以下游不需要自己维护请求表就能把
响应对回请求。

`withtime_utils::keyify<A,Env>(A &&a)` 在 `WithTimeData.hpp:201`，就是 `Key<A,Env>{std::move(a)}`
的一行封装，用于把普通数据流转成可投递给 facility 的 tagged 流。

在 app 类型内部还有便捷别名 `M::Key<T>` 与 `M::KeyedData<A,B>`（Env 已绑定），日常只用这两个。

### 普通 OnOrderFacility

类型定义 `RealTimeApp.hpp:1797`：`OnOrderFacility<A,B> = TwoWayHolder<AbstractOnOrderFacility<A,B>,A,B>`。
抽象基类 `AbstractOnOrderFacility` 在 `RealTimeApp.hpp:523`，继承
`IHandler<Key<A>>` 与 `OnOrderFacilityProducer<KeyedData<A,B>>`。

四个 lift 入口，与 action 的形态矩阵一一对应（见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md)）：

| 函数 | 行号 | 业务函数签名 |
|---|---|---|
| `liftPureOnOrderFacility<A>(f, liftParam)` | `RealTimeApp.hpp:1800` | `B(A&&)` |
| `liftMaybeOnOrderFacility<A>(f, liftParam)` | `RealTimeApp.hpp:1809` | `std::optional<B>(A&&)` |
| `enhancedMaybeOnOrderFacility<A>(f, liftParam)` | `RealTimeApp.hpp:1818` | `std::optional<B>(std::tuple<TimePoint,A>&&)` |
| `kleisliOnOrderFacility<A>(f, liftParam)` | `RealTimeApp.hpp:1827` | `M::Data<B>(M::InnerData<A>&&)` |

注意业务函数收到的是**裸 `A`**（不是 `Key<A>`），返回**裸 `B`**（不是 `KeyedData`）——
tag 的提取与回填由框架完成。这正是 pure facility 写起来和普通函数一样简单的原因。

`liftPureOnOrderFacility` 的真实签名（`RealTimeApp.hpp:1799-1801`）：

```cpp
template <class A, class F>
static auto liftPureOnOrderFacility(F &&f, LiftParameters<TimePoint> const &liftParam = LiftParameters<TimePoint>())
    -> std::shared_ptr<OnOrderFacility<A,decltype(f(std::declval<A>()))>>;
```

`GenericLift<M>::liftFacility(f)`（`tm_infra/tm_kit/infra/GenericLift.hpp:445`）可按签名自动选择这四者，
对应偏特化在 `GenericLift.hpp:284`/`292`/`300`/`311`。

### WithStart 变体

| 函数 | 行号 |
|---|---|
| `liftPureOnOrderFacilityWithStart<A>(f, startF, liftParam)` | `RealTimeApp.hpp:1841` |
| `liftMaybeOnOrderFacilityWithStart<A>(f, startF, liftParam)` | `RealTimeApp.hpp:1850` |
| `enhancedMaybeOnOrderFacilityWithStart<A>(f, startF, liftParam)` | `RealTimeApp.hpp:1859` |
| `kleisliOnOrderFacilityWithStart<A>(f, startF, liftParam)` | `RealTimeApp.hpp:1868` |

`startF` 的用途：这些变体的实现类 `OnOrderFacilityCoreWithStart`
（`RealTimeApp.hpp:1696`、`1698`、`1742`）**额外继承 `IExternalComponent`**，因此会被 AppRunner
在图启动阶段调用；`startF_(env)` 在 `RealTimeApp.hpp:1730`（threaded 版）与 `1772`（非 threaded 版）
被执行一次，参数是 Environment 指针。

用法场景：facility 需要在开始处理请求之前做一次初始化——连接外部系统、订阅行情、预热缓存。
不带 WithStart 的普通 facility 没有 `IExternalComponent` 身份，拿不到这个启动回调。

### LocalOnOrderFacility

facility + exporter 的捆绑，**额外接收一路辅助输入**（如状态更新），用于让 facility 的响应依赖
外部喂进来的数据。

- 类型别名 `RealTimeApp.hpp:2822`：`ThreeWayHolder<AbstractOnOrderFacility<Q,R>, ..., AbstractExporter<DataInputType>, DataInputType>`
- `localOnOrderFacility(facilityPtr, exporterPtr)` —— `RealTimeApp.hpp:2827`
- `AbstractIntegratedLocalOnOrderFacility<Q,R,D>` —— `RealTimeApp.hpp:2834`，让一个类同时实现两边
- `localOnOrderFacility(integratedPtr)` —— `RealTimeApp.hpp:2842`
- `localOnOrderFacility(Fac&&, Exp&&)` —— `RealTimeApp.hpp:2847`，从已有的 facility 与 exporter 组装
- `wrappedLocalOnOrderFacility(toWrap, inputT, outputT)` —— `RealTimeApp.hpp:2867`
- `simpleWrappedLocalOnOrderFacility(toWrap, inputT, outputT)` —— `RealTimeApp.hpp:2893`

源码在 `RealTimeApp.hpp:2806-2820` 解释了为何用"两个指针的元组"而非单一对象：为了让 facility 分支
与 exporter 分支能分别被组合。代价是 `LocalOnOrderFacility` **不管理这两个指针的内存**
（它无法知道是同一对象还是两个对象）；源码的理由是这些对象都应活到程序结束。

### OnOrderFacilityWithExternalEffects

facility + importer 的捆绑，是 `LocalOnOrderFacility` 的对偶（源码原话 "the dual of
LocalOnOrderFacility"，`RealTimeApp.hpp:2914`）：facility 除了响应请求，还会**主动往图里推数据**。

- 类型别名 `RealTimeApp.hpp:2923`
- `onOrderFacilityWithExternalEffects(facilityPtr, importerPtr)` —— `RealTimeApp.hpp:2928`
- `AbstractIntegratedOnOrderFacilityWithExternalEffects<Q,R,D>` —— `RealTimeApp.hpp:2935`
- `onOrderFacilityWithExternalEffects(integratedPtr)` —— `RealTimeApp.hpp:2945`
- 组装版 —— `RealTimeApp.hpp:2951`；`wrapped...` —— `2970`；`simpleWrapped...` —— `2996`

注意命名陷阱，源码注释 `RealTimeApp.hpp:2917-2921` 已说明：模板参数叫 `DataInputType`，
但它实际是**从 facility 流出**的数据类型；"input" 是从图外部视角看的叫法，为避免大量改动而保留。

### VIEOnOrderFacility

facility + exporter + importer 三合一，即前两者的并集。源码注释
（`RealTimeApp.hpp:3018-3022`）说明 VIE 之名来自"看起来像本地 facility，却有复杂的境外连接"。

- 类型别名 `RealTimeApp.hpp:3024`（`FourWayHolder`）
- `vieOnOrderFacility(facilityPtr, exporterPtr, importerPtr)` —— `RealTimeApp.hpp:3030`
- `AbstractIntegratedVIEOnOrderFacility<Q,R,ExtraIn,ExtraOut>` —— `RealTimeApp.hpp:3038`
  （别名 `AbstractIntegratedVIEOnOrderFacilityWithPublish` 在 `3047`）
- `vieOnOrderFacility(integratedPtr)` —— `RealTimeApp.hpp:3049`
- 组装版 —— `RealTimeApp.hpp:3055`；`wrappedVIEOnOrderFacility` —— `3078`；
  `simpleWrappedVIEOnOrderFacility` —— `3107`

这里 "input" / "output" 是**从 VIE facility 自身视角**看的（`RealTimeApp.hpp:3022`），与
`OnOrderFacilityWithExternalEffects` 的外部视角命名相反，混用时要特别小心。

### 包装与变换

| 函数 | 行号 | 说明 |
|---|---|---|
| `wrappedOnOrderFacility<I0,O0,I1,O1>(toWrap, inputT, outputT)` | `RealTimeApp.hpp:1972` | 用两个 action 转换输入输出类型，`Action<Key<I0>,Key<I1>>` 与 `Action<Key<O1>,Key<O0>>` |
| `simpleWrappedOnOrderFacility<I0,O0,Fac>(toWrap, inputT, outputT)` | `RealTimeApp.hpp:2066` | 用两个普通函数转换；`outputT` 形如 `O0(Fac::InputType const &, Fac::OutputType &&)` |
| `fromAbstractAction<A,B>(ptr)` | `RealTimeApp.hpp:1882` | 从手写的 `AbstractAction` 子类构造 action |
| `fromAbstractOnOrderFacility<A,B>(ptr)` | `RealTimeApp.hpp:1886` | 从手写的 `AbstractOnOrderFacility` 子类构造 facility |

`wrappedOnOrderFacility` 走 action，所以转换本身也是图节点，可以带时间语义；
`simpleWrappedOnOrderFacility` 走普通函数，更轻量。注意后者的 `outputT` 能同时看到**原始请求**
（第一参数）与响应（第二参数），便于做需要上下文的转换。

`fromAbstractOnOrderFacility` 是实现"异步响应"facility 的唯一途径：pure/maybe 形态必须在函数返回时
就给出响应，而手写 `AbstractOnOrderFacility` 子类可以在 `handle()` 里记下 tag、稍后在别的线程调
`publish()`。

### FacilitioidConnector 与 FacilityWrapper

这两个类型是本章最重要的抽象，都定义在 `AppRunner` 内部（`tm_infra/tm_kit/infra/WithTimeData.hpp`）：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:760-777
template <class A, class B>
using FacilitioidConnector =
    std::function<void(AppRunner &, Source<typename App::template Key<A>> &&, std::optional<Sink<typename App::template KeyedData<A,B>>> const &)>;
template <class A, class B>
using FacilityWrapper =
    std::optional<std::function<void(AppRunner &, OnOrderFacilityPtr<A,B> const &)>>;
template <class A, class B, class C>
using LocalFacilityWrapper =
    std::optional<std::function<void(AppRunner &, LocalOnOrderFacilityPtr<A,B,C> const &)>>;
template <class A, class B, class C>
using FacilityWithExternalEffectsWrapper =
    std::optional<std::function<void(AppRunner &, OnOrderFacilityWithExternalEffectsPtr<A,B,C> const &)>>;
template <class A, class B, class C, class D>
using VIEFacilityWrapper =
    std::optional<std::function<void(AppRunner &, VIEOnOrderFacilityPtr<A,B,C,D> const &)>>;
template <class A, class B>
using FacilitioidConnectorWrapper =
    std::optional<std::function<void(AppRunner &, FacilitioidConnector<A,B> const &)>>;
```

两者方向相反，这是理解它们的关键：

- **`FacilitioidConnector<A,B>`：我是调用方。** 它是"给我一个请求流和一个响应 sink，我负责把它们接到
  某个 facility 上"的函数。业务代码持有它并调用，完全不知道背后是本地函数还是远程 RPC。
- **`FacilityWrapper<A,B>`：我是提供方。** 它是"给我一个 facility，我负责把它暴露出去"的函数
  （通常是包装成 RPC 服务端）。类型是 `std::optional`，所以"不暴露"直接传 `std::nullopt`。

`AppRunner` 提供把具体 facility 转成 `FacilitioidConnector` 的静态函数，四变体各一个，
且都有同名重载 `facilityConnector`：

| 函数 | 行号 |
|---|---|
| `facilityConnector(OnOrderFacilityPtr<A,B>)` | `WithTimeData.hpp:3014` |
| `localFacilityConnector(LocalOnOrderFacilityPtr<A,B,C>)` | `WithTimeData.hpp:3024` |
| `facilityWithExternalEffectsConnector(...)` | `WithTimeData.hpp:3034` |
| `vieFacilityConnector(...)` | `WithTimeData.hpp:3044` |
| `facilityConnector(LocalOnOrderFacilityPtr<A,B,C>)` | `WithTimeData.hpp:3054` |
| `facilityConnector(OnOrderFacilityWithExternalEffectsPtr<A,B,C>)` | `WithTimeData.hpp:3058` |
| `facilityConnector(VIEOnOrderFacilityPtr<A,B,C,D>)` | `WithTimeData.hpp:3062` |

实现都是同一个模式（`WithTimeData.hpp:3014-3022`）：包一个 lambda，`sink` 有值时调
`placeOrderWith...`，无值时调 `...AndForget`。

相关的还有 `addNamedFacility(name, FacilitioidConnector<A,B>)`（`WithTimeData.hpp:1021`）与
`connectFacilitioidToAllPossiblePlaces(f)`（`WithTimeData.hpp:2420`）。

### 下单 API

`AppRunner` 的成员函数，每个都有"带 name"与"不带 name"两个重载，以及 `...AndForget` 版本
（不接收响应，只投递请求）：

| 函数 | 带 name | 不带 name |
|---|---|---|
| `placeOrderWithFacility` | `WithTimeData.hpp:1857` | `1878` |
| `placeOrderWithFacilityAndForget` | `WithTimeData.hpp:1899` | `1912` |
| `placeOrderWithLocalFacility` | `WithTimeData.hpp:1925` | `1954` |
| `placeOrderWithLocalFacilityAndForget` | `WithTimeData.hpp:1979` | `2000` |
| `placeOrderWithFacilityWithExternalEffects` | `WithTimeData.hpp:2017` | `2046` |
| `placeOrderWithFacilityWithExternalEffectsAndForget` | `WithTimeData.hpp:2071` | `2092` |
| `placeOrderWithVIEFacility` | `WithTimeData.hpp:2109` | `2140` |
| `placeOrderWithVIEFacilityAndForget` | `WithTimeData.hpp:2166` | `2189` |

签名形如（`WithTimeData.hpp:1857-1861`）：

```cpp
template <class Fac>
void placeOrderWithFacility(
    Source<Key<typename withtime_utils::OnOrderFacilityTypeInfo<App,Fac>::InputType, StateT>> &&input
    , std::string const &name
    , std::shared_ptr<Fac> const &f
    , Sink<KeyedData<...InputType, ...OutputType, StateT>> const &sink);
```

带 name 的版本会顺便完成注册（`registerOnOrderFacility_`，`WithTimeData.hpp:1864`），
不带 name 的版本要求 facility 已注册过（`checkName_`，`WithTimeData.hpp:1885`）。

## 最小可用示例

### pure facility：三行实现一个服务

```cpp
// 来源：tm_examples/synthetic_facility_test/main.cpp:82-86
using GL = infra::GenericLift<M>;
auto f = GL::liftFacility([](int x) -> double {
    return x*2.0;
});
r.registerOnOrderFacility("facility", f);
```

### FacilitioidConnector：实时用远程、回测用本地

这是本章最重要的模式。业务逻辑 `MainLogicCombination` 只声明自己需要一个 facilitioid：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:11-18（节选）
template <class R>
struct MainLogicInput {
    using M = typename R::AppType;
    typename R::template FacilitioidConnector<simple_demo::CalculateCommand, simple_demo::CalculateResult> commandConnector;
    std::vector<typename R::template FacilityWrapper<std::tuple<std::string, simple_demo::ConfigureCommandPOCO>, simple_demo::ConfigureResultPOCO>> configWrappers;
    typename R::template FacilityWrapper<simple_demo::OutstandingCommandsQuery, simple_demo::OutstandingCommandsResult> queryWrapper;
    typename R::template FacilityWrapper<std::tuple<std::string, simple_demo::ClearCommands>, simple_demo::ClearCommandsResult> clearCommandsWrapper;
};
```

使用处只是把它当函数调用，传入请求 source 与响应 sink：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:93-98
auto keyify = M::template liftPure<simple_demo::CalculateCommand>(dev::cd606::tm::infra::withtime_utils::keyify<simple_demo::CalculateCommand, typename M::EnvironmentType>);
input.commandConnector(
    r,
    r.execute("keyify", keyify, std::move(cmd)),
    r.actionAsSink(extractResult)
);
```

而由调用者决定它到底是什么。实时模式下是跨进程的远程 facility：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:101-116
R::FacilitioidConnector<CalculateCommand,CalculateResult> calc;
if (isReal) {
    calc =
        transport::MultiTransportRemoteFacilityManagingUtils<R>
        ::setupOneNonDistinguishedRemoteFacility<CalculateCommand, CalculateResult>(
            r
            , heartbeatSource.clone()
            , std::regex("simple_demo plain Calculator")
            , "calculator facility"
        ).facility;
} else {
    calc = &(MockCalculatorCombination<
                R
                ,basic::real_time_clock::ClockOnOrderFacility<TheEnvironment>
            >::service);
}
```

回测模式下是本地 mock：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:237-245
MainLogicInput<R> combinationInput {
    &(MockCalculatorCombination<
            R
            ,basic::top_down_single_pass_iteration_clock::ClockOnOrderFacility<TheEnvironment>
        >::service)
    , {}
    , std::nullopt
    , std::nullopt
};
```

类型检查模式下甚至是一个就地 lift 的 pure facility：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:282-290
auto facility = M::liftPureOnOrderFacility<CalculateCommand>(
    [](CalculateCommand &&) -> CalculateResult {
        return CalculateResult {};
    }
);
r.registerOnOrderFacility("facility", facility);

MainLogicInput<R> combinationInput {
    r.facilityConnector(facility)
    , ...
```

**三种截然不同的后端，业务代码一行不改。** 注意 `MockCalculatorCombination::service` 是个普通静态
函数，取地址即可当 `FacilitioidConnector` 用——因为它的签名正好匹配
`void(R&, Source<Key<A>>&&, std::optional<Sink<KeyedData<A,B>>> const&)`：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MockCalculatorCombination.hpp:19-23
static void service(
    R &r
    , typename R::template Source<MockInput> &&source
    , std::optional<typename R::template Sink<MockOutput>> const &sink)
```

函数体内根据 `sink` 是否有值分别调用两种下单 API，这正是 `facilityConnector` 的手写版：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MockCalculatorCombination.hpp:64-75
if (sink) {
    r.placeOrderWithFacility(
        r.execute("createFacilityKey", createFacilityKey, std::move(source))
        , "clockFacility", clockFacility
        , r.actionAsSink("facilityCallback", facilityCallback)
    );
    r.connect(r.actionAsSource(facilityCallback), *sink);
} else {
    r.placeOrderWithFacilityAndForget(
        r.execute("createFacilityKey", createFacilityKey, std::move(source))
        , "clockFacility", clockFacility
    );
}
```

### FacilityWrapper：把本地 facility 暴露为 RPC 服务

提供方视角。业务代码只在 wrapper 非空时才创建 facility 并交给它：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:118-127
if (input.queryWrapper) {
    auto queryFacility = M::template liftPureOnOrderFacility<
        simple_demo::OutstandingCommandsQuery
    >(
        boost::hana::curry<2>(std::mem_fn(&MainLogic::queryOutstandingCommands))(mainLogicPtr.get())
    );
    r.registerOnOrderFacility("queryFacility", queryFacility);
    (*input.queryWrapper)(r, queryFacility);
    r.markStateSharing(queryFacility, logic, "outstanding_cmds");
}
```

调用方填入具体传输：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:132-136
transport::MultiTransportFacilityWrapper<R>::facilityWrapper
    <OutstandingCommandsQuery,OutstandingCommandsResult>(
    "rabbitmq://127.0.0.1::guest:guest:test_query_queue"
    , "query_wrapper_"
)
```

回测时传 `std::nullopt`（`MainLogic.cpp:243-244`），整段 facility 代码连带 RabbitMQ 依赖一起消失。

`markStateSharing`（`WithTimeData.hpp:2999`）在这里是必需的：`queryFacility` 与 `logic` 共享同一个
`MainLogic` 对象的 `outstanding_cmds` 状态，需要告知 AppRunner 以便图校验与可视化正确反映这层耦合。

一个 facility 可以被多个 wrapper 同时暴露，此时要调
`setMaxOutputConnectivity`（`WithTimeData.hpp:2242`）放宽输出连接数限制：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:103-117（节选）
for (auto const &cw : input.configWrappers) {
    if (cw) {
        if (!cfgFacility) {
            cfgFacility = M::template liftPureOnOrderFacility<...>(...);
            r.registerOnOrderFacility("cfgFacility", cfgFacility);
            r.markStateSharing(cfgFacility, logic, "enabled");
            r.setMaxOutputConnectivity(cfgFacility, input.configWrappers.size());
        }
        (*cw)(r, cfgFacility);
    }
}
```

`MainLogic.cpp:120-131` 给它填了两个 wrapper：一个 RabbitMQ + proto，一个 JSON REST。

### 异步响应 facility：fromAbstractOnOrderFacility

pure facility 必须同步返回。要实现"请求发出去，响应稍后从别的线程回来"，手写子类：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/Calculator.cpp:41-97（已简化）
class CalculatorFacility final : public M::IExternalComponent, public M::AbstractOnOrderFacility<std::tuple<std::string, CalculateCommand>,CalculateResult>, public CalculateResultListener {
private:
    TheEnvironment *env_;
    Calculator calc_;
    std::unordered_map<int, TheEnvironment::IDType> idLookup_;
    std::mutex mutex_;
public:
    virtual void start(TheEnvironment *env) override final {
        env_ = env;
        calc_.start(this);
    }
    virtual void handle(M::InnerData<M::Key<std::tuple<std::string, CalculateCommand>>> &&data) override final {
        std::lock_guard<std::mutex> _(mutex_);
        idLookup_.insert({std::get<1>(data.timedData.value.key()).id(), data.timedData.value.id()});
        // ... 把请求转给外部的 calc_，不在此处产出响应
    }
    virtual void onCalculateResult(CalculatorOutput const &result) override final {
        // 外部回调线程：查出当初的 tag，再 publish
        bool isFinalResponse = (res.result() <= 0);
        // ... envID = idLookup_ 中查到的 ID
        publish(env_, M::Key<CalculateResult> {envID, res}, isFinalResponse);
    }
};

auto facility = M::fromAbstractOnOrderFacility(new CalculatorFacility());
r.registerOnOrderFacility("calculator facility", facility);
```

三个要点：

1. **tag 必须自己存。** `handle()` 里把 `data.timedData.value.id()`（Environment 生成的 ID）记进
   `idLookup_`，响应时用双参构造 `M::Key<CalculateResult>{envID, res}` 原样带回。
2. **`publish` 的第三个参数是 final 标记。** 一个请求可以对应多个响应；`isFinalResponse` 为 true 表示
   这是最后一个，下游可据此释放资源。这就是 on-order facility "零个或多个输出"的含义。
3. **额外继承 `M::IExternalComponent`** 才能拿到 `start(env)` 回调。若用 lift 形态，对应的是
   `...WithStart` 变体。

多响应的更简形式见 `tm_examples/synthetic_facility_test/main.cpp:160-171`，`handle()` 里起个线程，
先 publish 一个非 final、500ms 后 publish 一个 final。

### localOnOrderFacility

```cpp
// 来源：tm_examples/clock_logic_test/ClockLogicMain.hpp:47
auto facility = M::localOnOrderFacility(new Facility<M>());
```

这里传的是单个 `AbstractIntegratedLocalOnOrderFacility` 子类指针，走 `RealTimeApp.hpp:2842` 的重载。
随后它在 `DeclarativeGraph` 里既作为 facility 被下单，又作为 exporter 接收辅助输入：

```cpp
// 来源：tm_examples/clock_logic_test/ClockLogicMain.hpp:99-106（节选）
, {"facility", facility}
//connections
, {"oneShot1", "converter"}, {"converter", "facility", "print2"}   // 下单：source, facility, sink
, {"oneShot2", "facility"}                                          // 辅助输入：当 exporter 用
```

## 实时 / 回测行为差异

| 维度 | RealTimeApp | TopDownSinglePassIterationApp |
|---|---|---|
| 响应时机 | 可异步：`handle()` 返回后另一线程 `publish` | 必须在当次迭代内确定，无真正的异步 |
| `SuggestThreaded` | 生效，facility 可独占线程 | 忽略 |
| `DelaySimulator` | 忽略 | 生效（但注意：源码注释说明 `FireOnceOnly` 对 facility 无效，延迟模拟仍适用） |
| 远程 facility | 可用（RabbitMQ / Redis / gRPC / NATS 等） | 通常不可用，需换成本地 mock |
| 环检测 | 含 facility 的环只告警 | 同样只告警（`CannotHaveLoopEvenWithFacilities == false`） |
| 典型 facility 来源 | `setupOneNonDistinguishedRemoteFacility` 等远程工具 | `liftPureOnOrderFacility` 或 mock facilitioid |

实践要点：**facility 是实时与回测的主要分界面**。业务代码用 `FacilitioidConnector` 把这条缝隙
显式化，在 `main` 里按模式填不同实现。`MainLogic.cpp` 的
`run_real_or_virtual()` / `run_backtest()` / `run_typecheck()` 三个函数就是三种填法。

回测里替代远程 facility 的 mock 常用时钟 facility 来模拟响应延迟：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MockCalculatorCombination.hpp:24-28
auto clockFacility = ClockFacility::template createClockCallback<simple_demo::CalculateCommand, bool>(
    [](std::chrono::system_clock::time_point const &, std::size_t thisIdx, std::size_t totalCount) {
        return (thisIdx+1 >= totalCount);
    }
);
```

`ClockFacility` 是模板参数，实时模式传 `basic::real_time_clock::ClockOnOrderFacility`，
回测传 `basic::top_down_single_pass_iteration_clock::ClockOnOrderFacility`
（见 `MainLogic.cpp:114` 与 `240`）。同一个 mock 在两种模式下都能用。

## 易错点

- **禁用的 Key 特化是空类，报错很间接。** `Key<T*,Env>`、`Key<std::unique_ptr<T>,Env>`、
  `Key<Key<T,Env>,Env>` 都是空类（`WithTimeData.hpp:126-130`），误用时编译器抱怨的是缺少
  `key()` / `id()` 成员，而不是"不允许这样用"。看到这类报错先检查 key 类型里有没有裸指针或嵌套 Key。
- **响应必须沿用原 tag。** 手写 facility 时要用 `Key<B>{originalId, value}` 双参构造。
  若误用单参构造，`Env::new_id()` 会生成新 ID，响应永远匹配不回请求，表现为"请求发出去就没下文"。
- **`FireOnceOnly` 对 facility 无效。** `WithTimeData.hpp:62-64` 注释明确："This only applies to
  actions, not to on-order facilities"。
- **`OnOrderFacilityWithExternalEffects` 的 `DataInputType` 实际是输出。** 源码注释
  `RealTimeApp.hpp:2917-2921` 承认这是历史命名。而 `VIEOnOrderFacility` 的 in/out 又是自身视角
  （`RealTimeApp.hpp:3022`），两者方向相反。
- **`LocalOnOrderFacility` 不管理指针内存。** 见 `RealTimeApp.hpp:2806-2820`。传进去的对象必须活到
  程序结束，别传栈上对象。
- **一个 facility 接多个 wrapper 需要先放宽连接数。** 不调 `setMaxOutputConnectivity`
  会在 `finalize()` 时报连接数超限——注册 facility 时默认上限是 1
  （`WithTimeData.hpp:1195` 的 `setMaxOutputConnectivity_(name, 1)`）。
- **共享状态要显式声明。** 多个 facility 操作同一个业务对象时调 `markStateSharing`，
  否则图校验与 Graphviz 输出看不到这层依赖，容易误判成可以并行。
- **`AndForget` 版本不是"忽略响应"，而是根本不接响应 sink。** 如果 facility 仍会产出响应而无人消费，
  在严格的图校验下会报输出未连接。
- **`boost::hana::curry` 产物不能用 `GenericLift::liftFacility`。** 与 action 同理，
  `MainLogicCombination.hpp:245-246` 的注释已记录；必须显式写 `M::liftPureOnOrderFacility<...>`。
- **普通 facility 拿不到启动回调。** 需要初始化就用 `...WithStart` 变体，或手写子类并继承
  `IExternalComponent`。

## 第三方依赖

- [Boost.Hana](https://www.boost.org/doc/libs/release/libs/hana/doc/html/index.html)：示例用
  `boost::hana::curry<2>` 把成员函数绑成一元函数后 lift 成 facility。
- 远程 facility 的具体传输（RabbitMQ / Redis / NATS / gRPC / JSON REST）属 tm_transport 范畴，
  本章只涉及 `FacilitioidConnector` 这一层抽象。

## 相关章节

- [00-overview.md](00-overview.md) —— 数据流图总览与 facility 在其中的位置
- [01-app-types.md](01-app-types.md) —— `CannotHaveLoopEvenWithFacilities` 等 app 级常量
- [02-environments.md](02-environments.md) —— `Env::new_id()`、`IDType`、`DontCheckCycles`
- [03-nodes-and-lifting.md](03-nodes-and-lifting.md) —— lift 形态矩阵与 `LiftParameters`
- [05-app-runner.md](05-app-runner.md) —— `registerOnOrderFacility` / `markStateSharing` / `finalize` 的图校验
- [06-declarative-graph.md](06-declarative-graph.md) —— 用声明式语法下单与注册 facility
- [07-time-and-data.md](07-time-and-data.md) —— `InnerData` 与 final 标记
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
