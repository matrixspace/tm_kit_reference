---
title: CommonFlowUtils 节点组合工具
library: tm_basic
headers: [tm_kit/basic/CommonFlowUtils.hpp]
keywords: [CommonFlowUtilComponents, idFunc, bufferingNode, filterOnOptional, dispatchOneByOne, bunchWith, bunchWithProcessing, keyify, keyifyThroughCounter, shareBetweenDownstream, duplicateInput, preserveLeft, preserveRight, parallelArrow, fanOut, pureFilter, simpleFinalizer, simpleMovingTimeWindowKleisli, complexMovingTimeWindowActionKleisli, wholeHistoryFold, synchronizer2, keyedSynchronizer2, delayer, expediter, rightShift, leftShift, snapshotOnRight, collectAndPassDownOnRight, foldAndPassDownOnRight, groupByLookAhead, mergedImporter, shiftedImporter, pickOne, pickOneFromWrappedValue, wrapTuple2OnOrderFacilityBySupplyingDefaultValue, 通用流工具, 批处理, 时间窗口, 滑动窗口, 滑窗, 均值, 时序合并, 批聚合]
---

# CommonFlowUtils 节点组合工具

## 用途

`CommonFlowUtilComponents<M>` 是一个以 App 类型 `M` 为模板参数的工具集，所有方法均为 `static`，返回框架节点（`Action`、`Importer`、`Exporter`）供 `AppRunner` 连接。它弥补了 `tm_infra` 核心提升操作之外的常见数据流组合需求，包括批处理、时间窗口、同步合并、Key 化、时间移位等。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/CommonFlowUtils.hpp>

namespace dev::cd606::tm::basic {
    template <class M>
    class CommonFlowUtilComponents { ... };
}
```

`M` 通常是 `infra::RealTimeApp<TheEnvironment>`、`infra::SinglePassIterationApp<TheEnvironment>` 或 `infra::TopDownSinglePassIterationApp<TheEnvironment>`（三种 App 的类型别名统一为 `using M = ...`）。该类还需要 `TheEnvironment = typename M::EnvironmentType`。

## 核心类型与签名

### 1. 恒等、缓冲与过滤（`:45–107`）

```cpp
// :45 — 恒等 kleisli，不改变数据，主要用于传递 LiftParameters
template <class T>
static auto idFunc() -> std::function<typename M::template Data<T>(typename M::template InnerData<T>&&)>;

// :55 — 单项缓冲（暂存最后一个值并转发）
template <class T>
static std::shared_ptr<typename M::template Action<T,T>> bufferingNode();

// :60 — 透传 optional<T>，nullopt 即过滤掉
template <class T>
static std::shared_ptr<typename M::template Action<std::optional<T>,T>> filterOnOptional();

// :70 — 将 vector<T> 拆散为逐个 T 发出
template <class T>
static std::shared_ptr<typename M::template Action<std::vector<T>,T>> dispatchOneByOne();

// :79 — 将 vector<T> 以分段 vector<T> 发出（maxSegmentSize 控制分段大小）
template <class T>
static std::shared_ptr<typename M::template Action<std::vector<T>,std::vector<T>>> dispatchInSegments(std::size_t maxSegmentSize);
```

### 2. 包装器转换（`:120–145`）

```cpp
// :120 — 将 T 包进 SingleLayerWrapper<N,T>
template <int N, class T>
static std::shared_ptr<typename M::template Action<T, basic::SingleLayerWrapper<N,T>>> wrap();

// :128 — 将 SingleLayerWrapper<N,T> 解包为 T
template <int N, class T>
static std::shared_ptr<typename M::template Action<basic::SingleLayerWrapper<N,T>, T>> unwrap();

// :136 — 将 SingleLayerWrapper<N,T> 换层为 SingleLayerWrapper<M2,T>（N → M2）
template <int N, int M2, class T>
static std::shared_ptr<typename M::template Action<basic::SingleLayerWrapper<N,T>, basic::SingleLayerWrapper<M2,T>>> changeWrap();
```

### 3. 批处理（`:561–667`）

```cpp
// :561 — 将 T 不断积累，直到 T::isFinal() 返回 true，输出 vector<T>
template <class T>
static std::shared_ptr<typename M::template Action<T, std::vector<T>>> bunchWith();

// :564 — 同上，但通过自定义 Buncher 决定何时输出，以及如何聚合
// Buncher 需满足：
//   using OutputType = ...;
//   std::optional<OutputType> addOneItemAndCheckWhetherToOutput(T &&item);
template <class T, class Buncher>
static std::shared_ptr<typename M::template Action<T, typename Buncher::OutputType>> bunchWithProcessing();
```

**实现差异**：RealTimeApp 使用带 mutex 的后台线程类；SinglePassIterationApp 用 `continuationAction` + `State` 结构；TopDownSinglePassIterationApp 用独立 AbstractAction 子类（`:561`注释）。

### 4. Key 化族（`:567–700`）

```cpp
// :567 — 为 T 包装成 Key<T>（由环境生成 UUID）
template <class T>
static std::shared_ptr<typename M::template Action<T, infra::Key<T>>> keyify();

// :577 — 用函数 F 生成 key，F: (counter, T) -> KeyType
template <class T, class KeyType, class F>
static std::shared_ptr<typename M::template Action<T, infra::Key<T>>> keyifyThroughCounterFunc(F &&f);

// :611 — 用计数器 + 可选前缀生成字符串 key
template <class T>
static std::shared_ptr<typename M::template Action<T, infra::Key<T>>>
    keyifyThroughCounter(std::string const &prefix = "");

// :667 — 使用外部传入的 ID 包装（输入 pair<ID,T>）
template <class ID, class T>
static std::shared_ptr<typename M::template Action<std::pair<ID,T>, infra::Key<T>>>
    keyifyWithProvidedID();
```

### 5. 多路分发与合并（`:707–783`）

```cpp
// :707 — 复制到下游多路；输入 T 广播给所有连接到该节点的下游
template <class T>
static std::shared_ptr<typename M::template Action<T,T>> shareBetweenDownstream();

// :716 — 从 KeyedData<K,A> 提取 A
template <class K, class A>
static std::shared_ptr<typename M::template Action<infra::KeyedData<K,A>, A>> extractDataFromKeyedData();

// :726 — 从 KeyedData<K,A> 提取 pair<K,A>
template <class K, class A>
static std::shared_ptr<typename M::template Action<infra::KeyedData<K,A>, std::pair<K,A>>>
    extractIDAndDataFromKeyedData();

// :736 — 从 KeyedData<K,A> 提取 pair<string,A>（K 转 string）
template <class K, class A>
static std::shared_ptr<typename M::template Action<infra::KeyedData<K,A>, std::pair<std::string,A>>>
    extractIDStringAndDataFromKeyedData();

// :747 — 将 A 复制为 pair<A,A>（同一值发送给两路下游）
template <class T>
static std::shared_ptr<typename M::template Action<T, std::pair<T,T>>> duplicateInput();
```

### 6. 元组操作（`:764–800`）

```cpp
// :764 — 将 pair<A,B> 翻转为 pair<B,A>
template <class A, class B>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, std::pair<B,A>>> switchTupleOrder();

// :773 — 从 pair<A,B> 丢弃左侧，输出 B
template <class A, class B>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, B>> dropLeft();

// :782 — 从 pair<A,B> 丢弃右侧，输出 A
template <class A, class B>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, A>> dropRight();
```

### 7. 箭头组合（`:818–968`）

```cpp
// :818 — pair<A,B> 上只对 B 应用 F，A 原样透传，输出 pair<A, result_of_F>
// F: B -> B2
template <class A, class B, class F>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, std::pair<A, ...>>> preserveLeft(F &&f);

// :849 — pair<A,B> 上只对 A 应用 F，B 原样透传，输出 pair<result_of_F, B>
template <class A, class B, class F>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, std::pair<..., B>>> preserveRight(F &&f);

// :894 — 对 pair<A,B> 分别应用 F 和 G，输出 pair<result_of_F, result_of_G>
// ⚠️ 注释警告（:889）：名为"parallel"但不是真实并行——F 和 G 顺序执行
template <class A, class B, class F, class G>
static std::shared_ptr<typename M::template Action<std::pair<A,B>, std::pair<...,..>>> parallelArrow(F &&f, G &&g);

// :932 — 对 A 同时应用 F 和 G，输出 pair<result_of_F, result_of_G>
template <class A, class F, class G>
static std::shared_ptr<typename M::template Action<A, std::pair<...,..>>> fanOut(F &&f, G &&g);
```

### 8. Key/版本上下文包装（`:968–1163`）

```cpp
// :968 — F: A -> B；包装成 F': Key<A> -> KeyedData<A,B>
template <class A, class F>
static auto withKey(F &&f);

// :1005 — F: pair<K,A> -> B；包装成 F': Key<A> -> KeyedData<A,B>（K 为 Key 的 ID 类型）
template <class K, class A, class F>
static auto withKeyAndInput(F &&f);

// :1043 — F: A -> B；包装成输出 VersionedData<V,B>
template <class V, class A, class F>
static auto withVersion(F &&f);

// :1081 — F: A -> B；包装成输出 GroupedVersionedData<G,V,B>
template <class G, class V, class A, class F>
static auto withGroupAndVersion(F &&f);
```

### 9. 过滤族（`:1164–1176`）

```cpp
// :1164 — F: A const& -> bool；返回 std::nullopt 时过滤
template <class A, class F>
static auto pureFilter(F &&f);

// :1168 — F: A const& -> bool；环境也传给 F：F(env, A) -> bool
template <class A, class F>
static auto enhancedPureFilter(F &&f);

// :1172 — F: A const& -> bool；true → variant<A, std::monostate> 左路，false → 右路
template <class A, class F>
static auto pureTwoWayFilter(F &&f);

// :1176 — 带环境的双路版本
template <class A, class F>
static auto enhancedPureTwoWayFilter(F &&f);
```

### 10. 简单终止节点（`:1181`）

```cpp
// :1181 — 只允许第一个值通过（FireOnceOnly=true），后续全部丢弃
template <class T>
static std::shared_ptr<typename M::template Action<T,T>> simpleFinalizer();
```

### 11. 时间窗口与历史（`:1304–1382`）

```cpp
// :1304 — 滑动时间窗口的 kleisli；PushPopHandler 需要提供 push/pop 协议
// 输出由 PushPopHandler::output() 返回
template <class T, class PushPopHandler>
static auto simpleMovingTimeWindowKleisli(
    typename M::Duration const &windowSize,
    PushPopHandler &&handler,
    bool suggestThreaded = false
);

// :1311 — 复杂滑动窗口：输入 B 触发、窗口内存放 A 类型数据
template <class A, class B, class PushPopHandler>
static auto complexMovingTimeWindowActionKleisli(
    typename M::Duration const &windowSize,
    PushPopHandler &&handler,
    bool suggestThreaded = false
);

// PushPopHandler 协议（两者相同）：
// void push(typename M::TimePoint const &tp, T &&item);
// void pop(typename M::TimePoint const &tp, T const &item);
// OutputType output(typename M::TimePoint const &tp);

// :1347 — 累积全部历史；每次到来都调用 handler.addOne(tp, T&&)，并输出 handler.currentResult()
template <class T, class WholeHistoryHandler>
static auto wholeHistoryFold(WholeHistoryHandler &&handler, bool suggestThreaded = false);
```

### 12. 同步合并族（`:1532–1879`）

```cpp
// :1532 — FIFO 双路同步：等两路各有一个再配对调用 f(A,B)
// useMutex 控制实时模式的线程安全（默认与 M::PossiblyMultiThreaded 一致）
template <class A, class B, class F>
static std::shared_ptr<typename M::template Action<std::variant<A,B>, ...>>
    synchronizer2(F &&f, bool useMutex = M::PossiblyMultiThreaded);

// :1542 — 按 key 匹配的双路同步；keyExtractorA/B 分别从 A/B 提取同类型的 key
template <class A, class B, class KeyExtractorA, class KeyExtractorB, class F>
static std::shared_ptr<typename M::template Action<std::variant<A,B>, ...>>
    keyedSynchronizer2(KeyExtractorA &&keyExtractorA, KeyExtractorB &&keyExtractorB, F &&f);

// :1796 — 收集所有到来的 A，等 B 一到，将 vector<A> 和 B 传给 f，清空 A 列表
// 若 B 到来时 A 列表为空则丢弃 B
template <class A, class B, class F>
static std::shared_ptr<typename M::template Action<std::variant<A,B>, ...>>
    collectAndPassDownOnRight(F &&f, bool suggestThreaded = false);

// :1832 — 类似 collectAndPassDownOnRight，但对 A 做折叠（Folder）而非收集列表
// Folder: (FoldedType&, A&&) -> void；Outputter: (FoldedType&, B&&) -> optional<C>
template <class A, class B, class FoldedType, class Folder, class Outputter>
static std::shared_ptr<typename M::template Action<std::variant<A,B>, ...>>
    foldAndPassDownOnRight(Folder &&f, Outputter &&o, bool suggestThreaded = false);

// :1870 — 保存 A 的最新快照；每当 B 到来时，将最新 A 副本和 B 传给 f
// 若 B 先到（A 快照为空）则丢弃
template <class A, class B, class F>
static std::shared_ptr<typename M::template Action<std::variant<A,B>, ...>>
    snapshotOnRight(F &&f, bool suggestThreaded = false);
```

### 13. 时间移位（`:1551–1765`）

```cpp
// :1551 — 延迟 duration 后输出（实时：后台线程定时检查；回测：DelaySimulator）
template <class T>
static std::shared_ptr<typename M::template Action<T,T>>
    delayer(decltype(typename M::TimePoint{}-typename M::TimePoint{}) duration);

// :1651 — 实时模式下透传（左移在实时无意义）；回测模式下时间提前 duration
template <class T>
static std::shared_ptr<typename M::template Action<T,T>>
    expediter(decltype(typename M::TimePoint{}-typename M::TimePoint{}) duration);

// :1661 — 保存最新 N 项时间戳，当前值使用 N 步前的时间戳输出（时间向右移）
template <class T>
static std::shared_ptr<typename M::template Action<T,T>> rightShift(std::size_t steps);

// :1684 — 当前值使用 N 步前的时间戳输出（时间向左移）
// 实时模式：无意义，直接透传；回测：continuationAction（SinglePass）/ AbstractAction（TopDown）
template <class T>
static std::shared_ptr<typename M::template Action<T,T>> leftShift(std::size_t steps);
```

### 14. Variant 选择（`:1382–1416`）

```cpp
// :1382 — 从 VariantType（std::variant<...>）中提取 OneOfVariants，不匹配则过滤
template <class VariantType, class OneOfVariants>
static auto pickOne();

// :1399 — 从带 .value 的包装 variant 类型中提取 OneOfVariants
template <class WrappedVariantType, class OneOfVariants>
static auto pickOneFromWrappedValue();
```

### 15. 分组（`:1937`）

```cpp
// :1937 — 按 groupIdentifierFunc 分组；输入 tuple<T, optional<tuple<TimePoint,T>>>
// （当前项 + 前瞻下一项），相同组标识符的项合并为 vector<T> 输出
template <class T, class F>
static std::shared_ptr<typename M::template Action<
    std::tuple<T, std::optional<std::tuple<typename M::TimePoint, T>>>, std::vector<T>
>> groupByLookAhead(F &&groupIdentifierFunc, bool suggestThreaded = false);
```

### 16. Importer 合并与时移（`:2129–2220+`）

```cpp
// :2129 — 将多个 Importer<T> 合并为一个（按到达时间合并流）
template <class T>
static std::shared_ptr<typename M::template Importer<T>>
    mergedImporter(std::list<std::shared_ptr<typename M::template Importer<T>>> const &underlyingImporters);

// :2142 — 同上，附加比较器用于同一时间戳的排序（仅在回测模式中有意义）
template <class T, class Comparer>
static std::shared_ptr<typename M::template Importer<T>>
    mergedImporterWithComparer(std::list<std::shared_ptr<typename M::template Importer<T>>> const &underlyingImporters, Comparer const &comparer = Comparer());

// :2156 — 包装 Importer，对每个输出的时间戳加上 shiftBy
// ⚠️ 实时模式抛出 std::runtime_error（无意义）
template <class T>
static std::shared_ptr<typename M::template Importer<T>>
    shiftedImporter(std::shared_ptr<typename M::template Importer<T>> const &underlyingImporter, typename M::Duration const &shiftBy);
```

### 17. Facility 包装（`:1352`）

```cpp
// :1352 — 将 Tuple2OnOrderFacility<pair<A,B>, C> 包装成 OnOrderFacility<A, C>
// 即对 B 提供一个默认值，调用方只需传 A
template <class A, class B, class C>
static std::shared_ptr<typename M::template OnOrderFacility<A,C>>
    wrapTuple2OnOrderFacilityBySupplyingDefaultValue(
        std::shared_ptr<typename M::template OnOrderFacility<std::pair<A,B>,C>> const &f,
        B const &defaultB
    );
```

## 最小可用示例

### 滑动时间窗口（量化场景：5分钟均值）

```cpp
// 来源：tm_examples/time_window_test/TimeWindowTest.cpp（已简化）
#include <tm_kit/basic/CommonFlowUtils.hpp>
using M = infra::RealTimeApp<TheEnvironment>;
using CFU = basic::CommonFlowUtilComponents<M>;

// PushPopHandler 需持有窗口内数据并在 push/pop 时维护统计
struct SumPushPopHandler {
    double sum = 0.0;
    int count = 0;
    void push(typename M::TimePoint const &, double &&v) { sum += v; count++; }
    void pop(typename M::TimePoint const &, double const &v) { sum -= v; count--; }
    double output(typename M::TimePoint const &) { return count > 0 ? sum/count : 0.0; }
};

auto windowAction = CFU::template simpleMovingTimeWindowKleisli<double, SumPushPopHandler>(
    std::chrono::minutes(5), SumPushPopHandler{}
);
r.registerAction("5min_avg", windowAction);
```

### 双路同步合并（用 snapshotOnRight 实现行情+信号联动）

```cpp
// 来源：典型量化信号处理模式（已简化）
// 持续接受行情快照 A，每当信号 B 到来时，将最新 A 和 B 结合计算
using CFU = basic::CommonFlowUtilComponents<M>;
using MarketData = ...;
using Signal = ...;
using Order = ...;

auto combineAction = CFU::template snapshotOnRight<MarketData, Signal>(
    [](MarketData &&md, Signal &&sig) -> std::optional<Order> {
        if (sig.direction != 0) {
            return Order { md.lastPrice, sig.direction * 100 };
        }
        return std::nullopt;
    }
);
// 连接两路输入
r.execute2(combineAction, marketImporter, signalImporter);
```

### 批量收集后处理（bunchWith）

```cpp
// 来源：tm_examples/transaction_redundancy_test（已简化）
// 积累 5 条记录后批量处理
struct MyBuncher {
    using OutputType = std::vector<MyRecord>;
    std::vector<MyRecord> buf;
    std::optional<OutputType> addOneItemAndCheckWhetherToOutput(MyRecord &&item) {
        buf.push_back(std::move(item));
        if (buf.size() >= 5) {
            auto ret = std::move(buf);
            buf.clear();
            return ret;
        }
        return std::nullopt;
    }
};
auto bunchAction = CFU::template bunchWithProcessing<MyRecord, MyBuncher>();
```

### Importer 合并（回测多来源数据）

```cpp
// 来源：tm_examples 中多数据源回测（已简化）
// 将 tick 文件和 order 文件两个 importer 按时间戳合并
using CFU = basic::CommonFlowUtilComponents<M>;
auto merged = CFU::template mergedImporter<MarketTick>({tickImporter, orderImporter});
```

## 实时 / 回测行为差异

| 功能 | 实时 (`RealTimeApp`) | 回测 (`SinglePass`/`TopDown`) |
|---|---|---|
| `bunchWith` | 带 mutex 的后台线程类 | `continuationAction` + State / AbstractAction |
| `delayer(d)` | 后台线程轮询 `env->now()` | `DelaySimulator` 在事件队列中虚拟延迟 |
| `expediter(d)` | 透传（不支持提前） | `delayer(-d)`，时间戳前移 |
| `leftShift(n)` | 透传（无意义） | `continuationAction`（SinglePass）/ `AbstractAction`（TopDown） |
| `shiftedImporter` | 抛出 `std::runtime_error` | 时间戳偏移后输出 |
| `mergedImporter` | `IHandler`-based 扇入 | 优先队列按时间戳顺序合并 |
| `synchronizer2` | 可选 `useMutex=true` 加锁 | 单线程无竞争，`useMutex` 可为 `false` |

## 易错点

**1. `parallelArrow` 不是真并行**  
`:889` 的注释明确说明：`parallelArrow<A,B,F,G>` 名字中的"parallel"指"同时作用于 pair 的两个分量"，F 和 G 仍顺序执行，不是多线程并行。如需真正并行执行，应在 `RealTimeApp` 中用独立线程化的节点并通过 `shareBetweenDownstream` 分发输入。

**2. `synchronizer2` 使用 FIFO 匹配而非 key 匹配**  
`synchronizer2` 对两路到来的数据按 FIFO 顺序配对——A 流第一个与 B 流第一个配对，不考虑内容相关性。若需按业务 key 配对（如同一订单 ID），应使用 `keyedSynchronizer2`。

**3. `snapshotOnRight` 如果 B 比 A 先到则静默丢弃**  
若信号流（B）在行情流（A）首次到达之前就发来信号，`snapshotOnRight` 不会缓存该信号——快照为空直接返回 `nullopt`。回测回放时需保证 A 流时间戳早于 B 流，或改用 `synchronizer2`/`collectAndPassDownOnRight`。

**4. `bunchWith` 依赖 `T::isFinal()` 而 `bunchWithProcessing` 不依赖**  
`bunchWith<T>()` 通过调用 `item.isFinal()` 判断是否输出当前批次，因此 `T` 必须提供该方法。`bunchWithProcessing` 的触发条件完全由 `Buncher::addOneItemAndCheckWhetherToOutput` 决定，适合任意 `T`。

**5. `groupByLookAhead` 的输入类型含前瞻**  
该节点输入类型不是 `T` 而是 `tuple<T, optional<tuple<TimePoint,T>>>`（当前项 + 下一项预览）。需要在上游先用框架的预瞻机制（`LiftParameters::LookAheadProvider`）包装原始数据流，不能直接把普通 `T` 流接入。

**6. `rightShift` 使用静态局部 `deque`，线程不安全**  
`:1666` 的实现用了 `static std::deque<...>` 存储缓冲，这意味着：同一进程中若多处调用 `rightShift` 返回值连接到不同子图，会共享同一个缓冲区，产生数据混乱。每次需要不同的右移节点时，必须调用 `rightShift` 返回新实例，而不是复用一个 `shared_ptr`。

**7. `mergedImporterWithComparer` 仅在同时间戳排序时有效**  
`Comparer` 只用于打破同一时间戳的平局顺序，不会改变时间戳不同时的合并顺序。若需要完全自定义合并顺序，需要手写 AbstractImporter。

## 第三方依赖

`CommonFlowUtils.hpp` 全部依赖 `tm_infra` 核心接口，无直接第三方库依赖。内部用到了标准库的 `std::deque`、`std::priority_queue`、`std::mutex`，以及 `tm_infra` 的提升函数族（`M::template kleisli`、`M::template liftMaybe2`、`M::template continuationAction`）。

## 相关章节

- [节点提升与 Kleisli](../tm_infra/03-nodes-and-lifting.md) — `liftMaybe2`、`continuationAction`、`LiftParameters` 等提升原语
- [序列化格式](03-serialization.md) — 时间窗口内的数据通常配合 `KeyedData<K,A>` 传输，序列化格式在传输层决定
- [AppRunnerUtils](10-app-runner-utils.md) — 与 `CommonFlowUtils` 互补，偏向于 `AppRunner` 级的图构建工具
- [共享链](08-shared-chain.md) — 事件溯源场景中 `wholeHistoryFold` 常配合链读取使用
- [tm_basic 概览](00-overview.md)
