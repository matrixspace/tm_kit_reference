---
title: 节点创建与函数提升（lift）
library: tm_infra
headers: [tm_kit/infra/RealTimeApp.hpp, tm_kit/infra/TopDownSinglePassIterationApp.hpp, tm_kit/infra/SinglePassIterationApp.hpp, tm_kit/infra/BasicWithTimeApp.hpp, tm_kit/infra/WithTimeData.hpp, tm_kit/infra/GenericLift.hpp, tm_kit/infra/KleisliUtils.hpp, tm_kit/infra/KleisliSequence.hpp]
keywords: [lift, liftPure, liftMaybe, liftMulti, kleisli, enhanced, LiftParameters, SuggestThreaded, DelaySimulator, FireOnceOnly, importer, exporter, simpleImporter, triggerImporter, constFirstPushImporter, bunchedImporter, pureExporter, trivialExporter, compose, delayedImporter, lazyImporter, curtailedAction, passThroughAction, dispatchTupleAction, continuationAction, GenericLift, KleisliUtils, KleisliSequence, 提升, 节点创建]
---

# 节点创建与函数提升（lift）

## 用途

把普通 C++ 函数变成数据流图中的节点。这是日常开发中使用频率最高的一族 API：业务逻辑写成纯函数，
再用 lift 把它"提升"成 action；用 importer 族把外部数据引进图中；用 exporter 族把结果送出图外。

关键收益是业务函数本身不知道自己运行在实时模式还是回测模式——同一个 `MainLogic::runLogic` 在
`RealTimeApp` 下多线程跑，在 `TopDownSinglePassIterationApp` 下单线程回测跑，代码一行不改。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/RealTimeApp.hpp>                  // 实时模式
#include <tm_kit/infra/TopDownSinglePassIterationApp.hpp> // 回测模式
#include <tm_kit/infra/GenericLift.hpp>                   // 自动推导 lift 形态
#include <tm_kit/infra/KleisliUtils.hpp>
#include <tm_kit/infra/KleisliSequence.hpp>
```

命名空间：`dev::cd606::tm::infra`。

lift 系列是 app 类型的**静态成员函数**，惯例上先取别名再调用：

```cpp
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
auto action = M::liftPure<InputType>(f);
```

## 核心类型与签名

### lift 形态矩阵

四种基本形态，按"函数签名长什么样"选择：

| 形态 | 函数签名 | 产出 | 可控时间戳 |
|---|---|---|---|
| pure | `B(A &&)` | 必定一个 | 否（沿用输入时间） |
| maybe | `std::optional<B>(A &&)` | 零或一个 | 否 |
| multi | `std::vector<B>(A &&)` | 零到多个 | 否 |
| kleisli | `M::Data<B>(M::InnerData<A> &&)` | 零或一个 | 是 |

每种形态都有 enhanced 变体：函数的入参从 `A &&` 变成 `std::tuple<TimePoint, A> &&`，
即**额外收到该数据的时间戳**，但仍不能控制输出时间戳。需要控制输出时间戳必须用 kleisli。

`RealTimeApp` 中带 `1` 后缀的单输入版本：

- `liftPure1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1166`
- `liftMaybe1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1182`
- `enhancedMaybe1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1198`
- `kleisli1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1214`
- `liftMulti1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1408`
- `enhancedMulti1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1424`
- `kleisliMulti1` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1440`

实际签名（以 `liftPure1` 为例，`RealTimeApp.hpp:1166`）：

```cpp
template <class A, class F>
static auto liftPure1(F &&f, LiftParameters<TimePoint> const &liftParam = LiftParameters<TimePoint>())
    -> std::shared_ptr<Action<A,decltype(f(std::declval<A>()))>>;
```

注意输出类型由 `decltype` 推导，**只需显式给出输入类型 `A`**。

### 无后缀与 N 元版本

数字后缀表示输入分支数量，`liftPureN` 的输入类型是 `std::variant<A0,...,AN-1>`。
这些版本由 `*_Piece.hpp` 生成（见 [09-generated-pieces.md](09-generated-pieces.md)）：

- 无后缀 `liftPure` —— `tm_infra/tm_kit/infra/RealTimeApp_PureN_Piece.hpp:668`
- `liftPure2` —— `tm_infra/tm_kit/infra/RealTimeApp_PureN_Piece.hpp:21`
- 无后缀 `liftMaybe` —— `tm_infra/tm_kit/infra/RealTimeApp_MaybeN_Piece.hpp:763`
- `liftMaybe2` —— `tm_infra/tm_kit/infra/RealTimeApp_MaybeN_Piece.hpp:26`
- 无后缀 `enhancedMaybe` —— `tm_infra/tm_kit/infra/RealTimeApp_EnhancedMaybeN_Piece.hpp:763`
- `enhancedMaybe2` —— `tm_infra/tm_kit/infra/RealTimeApp_EnhancedMaybeN_Piece.hpp:26`
- 无后缀 `kleisli` —— `tm_infra/tm_kit/infra/RealTimeApp_KleisliN_Piece.hpp:668`
- 无后缀 `liftMulti` —— `tm_infra/tm_kit/infra/RealTimeApp_MultiN_Piece.hpp:763`
- 无后缀 `enhancedMulti` —— `tm_infra/tm_kit/infra/RealTimeApp_EnhancedMultiN_Piece.hpp:763`
- 无后缀 `kleisliMulti` —— `tm_infra/tm_kit/infra/RealTimeApp_KleisliMultiN_Piece.hpp:668`

`BasicWithTimeApp` 的对应入口集中在 `tm_infra/tm_kit/infra/BasicWithTimeApp.hpp:115-145`，
`SinglePassIterationApp` 在 `tm_infra/tm_kit/infra/SinglePassIterationApp.hpp:1202-1217` 与 `1336-1346`。

**无后缀版本等价于 1 元版本**，日常代码几乎只用无后缀形式；多输入才写 `liftMaybe2` 这类。

### LiftParameters&lt;TimePoint&gt;

定义在 `tm_infra/tm_kit/infra/WithTimeData.hpp:49`。它是**每个** lift / importer / exporter /
facility 工厂函数的最后一个可选参数，贯穿整套 API：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:49
template <class T>
struct LiftParameters {
    bool suggestThreaded = false;
    using DelaySimulatorType = std::optional<std::function<decltype(T()-T())(int, T const &)>>;
    DelaySimulatorType delaySimulator = std::nullopt;
    bool fireOnceOnly = false;

    LiftParameters &SuggestThreaded(bool s);
    LiftParameters &DelaySimulator(DelaySimulatorType const &d);
    LiftParameters &FireOnceOnly(bool f);
};
```

三个链式设置器返回 `*this`，可连写。源码注释已标明各自的适用范围，这点很重要：

| 字段 | 生效模式 | 语义 |
|---|---|---|
| `suggestThreaded` | 仅实时模式 | 该节点逻辑在自己的线程里执行 |
| `delaySimulator` | 仅单遍迭代模式 | 为该节点人为增加延迟，模拟"逻辑耗时" |
| `fireOnceOnly` | 两种模式 | 节点产出第一个输出后即停止；**只对 action 有效，对 facility 无效** |

`delaySimulator` 的 `int` 参数是**输入分支下标（0 起）**，因为不同输入可以有不同延迟。
返回值类型是 `decltype(T()-T())`，即时间点类型对应的 duration。

验证过的实现事实：`suggestThreaded` 在 `TopDownSinglePassIterationApp.hpp` 中出现 0 次，
`delaySimulator` 在 `RealTimeApp.hpp` 中出现 0 次。两者互不干扰，可以在同一个
`LiftParameters` 上都设置好，让同一份业务代码在两种模式下各取所需。

### importer 族（RealTimeApp）

| 函数 | 行号 | 说明 |
|---|---|---|
| `vacuousImporter<T>()` | `RealTimeApp.hpp:2174` | 永不产出数据，占位用 |
| `simpleImporter<T>(f, liftParam)` | `RealTimeApp.hpp:2183` | `f` 收到 `PublisherCall<T> &`，自行决定推送几次、何时返回 |
| `uniformSimpleImporter<T>(f, liftParam)` | `RealTimeApp.hpp:2236` | `f` 形如 `std::tuple<bool, M::Data<T>>(Env *)`，被循环调用，`bool` 为"是否还有下一个" |
| `constFirstPushImporter<T>(t)` | `RealTimeApp.hpp:2240` | 启动时推一个常量 |
| `constFirstPushKeyImporter<T>(t)` | `RealTimeApp.hpp:2247` | 同上但自动 `keyify`，产出 `Key<T>` |
| `constTriggerImporter<T,HasOwnThread>(t)` | `RealTimeApp.hpp:2253` | 返回 `tuple<importer, std::function<void()>>` |
| `triggerImporter<T,HasOwnThread>()` | `RealTimeApp.hpp:2346` | 返回 `tuple<importer, std::function<void(T&&)>>` |
| `triggerImporterWithTime<T,HasOwnThread>()` | `RealTimeApp.hpp:2442` | 同上，触发函数接受 `WithTime<T,TimePoint>&&`，可指定时间戳 |
| `bunchedImporter<T,NotUsed>(underlying, notUsed)` | `RealTimeApp.hpp:2551` | 包装另一个 importer，把多个 `T` 攒成 `std::vector<T>` |
| `importer<T>(AbstractImporter<T> *)` | `RealTimeApp.hpp:2170` | 从手写的 `AbstractImporter` 子类构造 |

`TopDownSinglePassIterationApp` 的对应入口在
`tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:1729`（`importer`）、`1733`（`vacuousImporter`）、
`1746`（`simpleImporter`）、`1750`（`uniformSimpleImporter`）、`1754`（`constFirstPushImporter`）、
`1776`（`constTriggerImporter`）、`1823`（`triggerImporter`）、`1869`（`triggerImporterWithTime`）、
`2042`（`bunchedImporter`）。

**trigger 系列是从图外注入数据的关键手法。** 它们返回 tuple，第二个元素是可以在任意线程调用的
触发函数——GUI 回调、第三方库回调、另一个 AppRunner 都能借此把数据塞进图里：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/FltkEnablerGUI.cpp:39
auto configureImporterAndFunc = M::triggerImporter<ConfigureCommand>();
auto configureImporter = std::get<0>(configureImporterAndFunc);
r.registerImporter("configureImporter", configureImporter);
configureFeedFunc = std::get<1>(configureImporterAndFunc);
```

`configureFeedFunc` 随后在 FLTK 按钮回调里被调用，数据即进入图中。

注意 `bunchedImporter` 的第二个参数在实时模式下签名为 `NotUsed &&`（默认 `std::monostate`，
`RealTimeApp.hpp:2551`），而在单遍迭代模式下是 `BunchSplitLogic &&`
（`TopDownSinglePassIterationApp.hpp:2042`）——实时模式按"当前攒到的全量"切分，不需要逻辑。

### exporter 族

| 函数 | 行号 | 说明 |
|---|---|---|
| `simpleExporter<T>(f, liftParam)` | `RealTimeApp.hpp:2627` | `f` 收到完整的 `InnerData<T> &&`（含时间戳与环境指针） |
| `pureExporter<T>(f, liftParam)` | `RealTimeApp.hpp:2635` | `f` 只收到 `T &&`，内部包装成 `simpleExporter` |
| `trivialExporter<T>()` | `RealTimeApp.hpp:2648` | 丢弃一切输入；用于满足"输出必须被消费"的图校验 |

单遍迭代模式对应 `TopDownSinglePassIterationApp.hpp:2227` / `2231` / `2244`。

### 组合器

| 函数 | 行号 | 说明 |
|---|---|---|
| `compose(Action<A,B>&&, Action<B,C>&&)` | `RealTimeApp.hpp:2112` | 两个 action 串成一个 |
| `composeImporter(Importer<T1>&&, Action<T1,T2>&&)` | `RealTimeApp.hpp:2654` | importer 接一个 action，结果仍是 importer |
| `composeExporter(Action<T1,T2>&&, Exporter<T2>&&)` | `RealTimeApp.hpp:2688` | action 接一个 exporter，结果仍是 exporter |
| `delayedImporter<T1,T2>(Importer<T2>&&)` | `RealTimeApp.hpp:2714` | 变成 `Action<T1,T2>`：收到第一个 `T1` 才启动内部 importer |
| `lazyImporter<T1,T2>(factory)` | `RealTimeApp.hpp:2749` | `Action<T1,T2>`：用收到的 `T1` 现场造 importer |
| `curtailedAction<T1,T2>(Action<T1,T2>&&)` | `RealTimeApp.hpp:2783` | 砍掉 action 的输出，变成 `Exporter<T1>` |
| `passThroughAction<T>()` | `RealTimeApp.hpp:1589` | 恒等 action；`T` 不能是 variant 或 `std::any`（`RealTimeApp.hpp:1586-1588` 的 `enable_if`） |
| `dispatchTupleAction<Ts...>()` | `RealTimeApp.hpp:1624` | `Action<std::tuple<Ts...>, std::variant<Ts...>>`：把 tuple 拆成逐个 variant 输出 |
| `continuationAction<A,B,ContinuationStructure>(cont, state, liftParam)` | `RealTimeApp.hpp:1540` | 由 `TimedAppModelContinuation` 驱动的带状态 action |

`delayedImporter` / `lazyImporter` / `curtailedAction` 在单遍迭代模式下分别位于
`TopDownSinglePassIterationApp.hpp:2333` / `2365` / `2401`。

### GenericLift&lt;M&gt;

`tm_infra/tm_kit/infra/GenericLift.hpp:24`。通过检查函数的 `operator()` 签名**自动推导该用哪种 lift**，
省掉显式写输入类型：

```cpp
// 入口：tm_infra/tm_kit/infra/GenericLift.hpp:415
template <class F>
static auto lift(F &&f, LiftParameters<typename M::TimePoint> const &liftParam = ...);
```

推导规则（`GenericLift.hpp:124-248` 的偏特化）：

| 函数签名 | 推导结果 |
|---|---|
| `B(A&&)` | `liftPure<A>` |
| `std::optional<B>(A&&)` | `liftMaybe<A>` |
| `std::optional<B>(std::tuple<TimePoint,A>&&)` | `enhancedMaybe<A>` |
| `M::Data<B>(M::InnerData<A>&&)` | `kleisli<A>` |
| `void(A&&)` | `pureExporter<A>` |
| `void(M::InnerData<A>&&)` | `simpleExporter<A>` |
| `std::tuple<bool, M::Data<A>>(Env*)` | `uniformSimpleImporter<A>` |
| `M::Data<A>(Env*)` | `uniformSimpleImporter<A>`（自动补 hasNext） |
| `std::tuple<bool, A>(Env*)` | `uniformSimpleImporter<A>`（自动包时间戳） |

**同一个 `GenericLift::lift` 既能产出 action，也能产出 importer 或 exporter**，视函数签名而定。
这是 `DeclarativeGraph` 能用统一语法声明各类节点的基础（见 [06-declarative-graph.md](06-declarative-graph.md)）。

multi / facility / 特殊节点需要显式标记类型（`GenericLift.hpp:10-16`）：

- `GenericLift<M>::liftMulti(f)` 或 `lift(LiftAsMulti{}, f)` —— `GenericLift.hpp:430` / `498`
- `GenericLift<M>::liftFacility(f)` 或 `lift(LiftAsFacility{}, f)` —— `GenericLift.hpp:445` / `506`
- `lift(DelayImporter<Trigger>{}, f)` —— `GenericLift.hpp:510`
- `lift(LazyImporter<Input>{}, f)` —— `GenericLift.hpp:515`
- `lift(CurtailAction{}, f)` —— `GenericLift.hpp:526`
- `liftKU(f)` —— `GenericLift.hpp:460`，产出 `KleisliUtils` 包装而非节点
- 自由函数 `liftAsMultiWrapper(f)` —— `GenericLift.hpp:19`，把 multi 标记与函数打包成 tuple 传递

#### GenericLift 的限制

`GenericLift` 依赖 `decltype(&F::operator())` 取唯一签名（`GenericLift.hpp:29`）。
若 `operator()` **重载**，推导失败。示例代码中给出了明确的真实踩坑记录：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:205-207
//GenericLift does not work with boost::hana::curry because
//the generated operator() in boost::hana::curry objects are
//overloaded
```

以及 `MainLogicCombination.hpp:245-246`：

```cpp
//The following lifts also cannot be done with GL::lift
//because overloaded operator() in boost::hana::curry is involved
```

因此凡用 `boost::hana::curry` 绑定成员函数的场合，**必须退回显式 `M::liftMaybe2<...>` /
`M::liftPureOnOrderFacility<...>` 写法**。此外 lambda 带 `auto` 参数（泛型 lambda）同样是模板化
`operator()`，也不可推导。

### KleisliUtils 与 KleisliSequence

`KleisliUtils<M>`（`tm_infra/tm_kit/infra/KleisliUtils.hpp:35`）提供**未实体化为节点**的中间表示：
先把多段逻辑在类型层面组合好，最后一次性变成单个 action。这样图上只多一个节点，而非每段一个。

包装入口：

- `KleisliUtils<M>::liftPure<A>(f)` —— `KleisliUtils.hpp:246`
- `liftMaybe<A>(f)` —— `KleisliUtils.hpp:250`
- `enhancedMaybe<A>(f)` —— `KleisliUtils.hpp:254`
- `kleisli<A>(f)` —— `KleisliUtils.hpp:258`
- `liftMulti<A>(f)` —— `KleisliUtils.hpp:262`
- `exporterFromPure<A>(f)` —— `KleisliUtils.hpp:274`
- `exporterHolder<A>(f)` —— `KleisliUtils.hpp:278`

组合与实体化：

- `compose(f, g)` —— `KleisliUtils.hpp:282` 是通用版本；其后 `290` 起是上百个形态组合的偏特化
  （pure→pure、pure→maybe、maybe→multi……），保证组合后仍是最窄的形态。
- `action(kleisliObj, liftParam)` —— `KleisliUtils.hpp:1457` 起的重载，把组合结果变成真正的 action。
  可见 `1457`-`1469` 都落到 `M::kleisli<A>`，`1473`-`1481` 落到 `M::kleisliMulti<A>`。

`KleisliSequence<M>::seq(...)`（`tm_infra/tm_kit/infra/KleisliSequence.hpp:12`）是 `compose` 的变参糖，
实现只有 10 行：

```cpp
// 来源：tm_infra/tm_kit/infra/KleisliSequence.hpp:11-21
template <class FirstF, class... Fs>
static auto seq(FirstF &&firstF, Fs &&... fs) {
    if constexpr (sizeof...(Fs) == 0) {
        return GenericLift<M>::liftKU(std::move(firstF));
    } else {
        return KleisliUtils<M>::compose(
            GenericLift<M>::liftKU(std::move(firstF))
            , seq<Fs...>(std::forward<Fs>(fs)...)
        );
    }
}
```

因为每一段都先过 `GenericLift<M>::liftKU`，**裸 lambda 可以直接作为 `seq` 的参数**，无需手工包装。
`liftKU` 对已经包装过的对象会原样返回（`GenericLift.hpp:466`，依据 `KleisliUtils<M>::IsAlreadyWrapped`，
定义于 `KleisliUtils.hpp:1494`），所以混用裸 lambda 与 `CommonFlowUtilComponents` 返回的 kleisli 对象都没问题。

## 最小可用示例

### enhanced lift + DelaySimulator（回测延迟模拟）

`MainLogic::runLogic` 的签名是
`std::optional<CalculateCommand>(std::tuple<time_point, std::variant<InputData, CalculateResult>> &&)`
（`tm_examples/simple_demo/program_logic/MainLogic.hpp:24-26`），即 enhanced + maybe + 2 元输入，
所以用 `enhancedMaybe2`：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:61-76
auto logic = M::template enhancedMaybe2<
        simple_demo::InputData
        , simple_demo::CalculateResult
    >(
        boost::hana::curry<2>(std::mem_fn(&MainLogic::runLogic))(mainLogicPtr.get())
        , dev::cd606::tm::infra::LiftParameters<std::chrono::system_clock::time_point>()
            .DelaySimulator(
                [](int which, std::chrono::system_clock::time_point const &) -> std::chrono::system_clock::duration {
                    if (which == 0) {
                        return std::chrono::milliseconds(100);
                    } else {
                        return std::chrono::milliseconds(0);
                    }
                }
            )
    );
```

这段代码是本章的核心范例，三点值得注意：

1. 两个模板参数 `InputData` 与 `CalculateResult` 对应 `std::variant` 的两个分支，顺序必须与业务函数
   的 variant 顺序一致。
2. `DelaySimulator` 里 `which == 0` 指第一个输入分支（`InputData`），给它 100ms 延迟；
   `CalculateResult` 分支（`which == 1`）不延迟。回测时这就复现了"行情到达后逻辑算了 100ms 才下单"。
3. `boost::hana::curry<2>(std::mem_fn(...))(ptr)` 把成员函数绑成一元可调用对象——正是前面提到的
   无法用 `GenericLift` 的那种对象。

### KleisliSequence 串联多段逻辑

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:169-204（已简化：省略各段的构造）
auto upToMainLogicInputKleisli = dev::cd606::tm::infra::KleisliSequence<M>
    ::seq(
        [](simple_demo::InputData &&d) -> double {
            return d.value();
        }
        , duplicator
        , exponentialAverageWithInputAttached
        , filterValue
        , assembleMainLogicInput
    );

using GL = dev::cd606::tm::infra::GenericLift<M>;
auto upToMainLogicInput = GL::lift(std::move(upToMainLogicInputKleisli));
```

`seq` 的第一段是裸 lambda，后面四段是 `CommonFlowUtilComponents<M>` 返回的 kleisli 对象，混用无碍。
最后 `GL::lift` 把整条链实体化为**一个** action。

同一文件 `MainLogicCombination.hpp:180-202` 保留了等价的 `KleisliUtils::compose` 嵌套写法（被注释掉），
对照价值很高——五段逻辑要写成四层嵌套的 `compose`，每层都得显式给出中间类型：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:188-201（原文为注释，节选）
auto upToMainLogicInputKleisli =
    dev::cd606::tm::infra::KleisliUtils<M>::template compose<simple_demo::InputData>(
        std::move(extractDouble)
        , dev::cd606::tm::infra::KleisliUtils<M>::template compose<double>(
            std::move(duplicator)
            , dev::cd606::tm::infra::KleisliUtils<M>::template compose<std::tuple<double,double>>(
                std::move(exponentialAverageWithInputAttached)
                , ...
            )
        )
    );
```

新代码用 `KleisliSequence::seq` 即可，不必手写嵌套。

### simpleImporter + SuggestThreaded

```cpp
// 来源：tm_examples/simple_demo_chain_version/executables/enable_client/LineNoiseMain.cpp:20-34
auto lineImporter = M::simpleImporter<std::string>(
    [](M::PublisherCall<std::string> &pub) {
        linenoiseHistorySetMaxLen(100);
        char *p;
        while ((p = linenoise(">>")) != nullptr) {
            if (p[0] != '\0') {
                linenoiseHistoryAdd(p);
            }
            pub(boost::trim_copy(std::string {p}));
        }
        pub("exit");
    }
    , infra::LiftParameters<std::chrono::system_clock::time_point>()
        .SuggestThreaded(true)
);
```

`linenoise` 是阻塞调用，所以必须 `SuggestThreaded(true)`，否则会卡住整个 app 的启动流程。
`PublisherCall<T>`（`RealTimeApp.hpp:2131`）在函数体内可多次调用，每次推送一个数据。

### uniformSimpleImporter 风格（GenericLift 自动识别）

```cpp
// 来源：tm_examples/common_flow_util_tests/KUSeqTest.cpp:24-38
auto importer(Env *e) -> std::tuple<bool, M::Data<int>> {
    static int ii = 0;
    ++ii;
    return {
        (ii < 10)
        , M::InnerData<int> {
            e
            , {
                ii
                , ii
                , (ii >= 10)
            }
        }
    };
}
```

函数签名是 `std::tuple<bool, M::Data<int>>(Env *)`，`GenericLift` 据此推导为
`uniformSimpleImporter<int>`。`InnerData` 的三个字段依次是时间点、值、final 标记；
这里时钟是 `int` 类型（`KUSeqTest.cpp:16` 用 `top_down_single_pass_iteration_clock::ClockComponent<int>`），
所以时间点直接写 `ii`。

### pureExporter

```cpp
// 来源：tm_examples/simple_demo/plain_executables/FltkEnablerGUI.cpp:47-64（已简化）
auto statusHandler = M::pureExporter<bool>(
    [status,enableBtn,disableBtn](bool &&data) {
        Fl::lock();
        if (data) { /* 更新 GUI */ }
        Fl::unlock();
        Fl::awake();
    }
);
r.registerExporter("statusHandler", statusHandler);
```

## 实时 / 回测行为差异

| 维度 | RealTimeApp | TopDownSinglePassIterationApp |
|---|---|---|
| `SuggestThreaded` | 生效：节点独占线程，上游 publish 后立即返回 | **完全忽略**（源码中无引用） |
| `DelaySimulator` | **完全忽略**（源码中无引用） | 生效：输出时间戳被推后，用于模拟逻辑耗时 |
| `FireOnceOnly` | 生效 | 生效 |
| 节点执行时机 | 挂钟时间驱动，各线程并发 | 数据驱动，单线程按时间序推进 |
| importer 行为 | `simpleImporter`/`uniformSimpleImporter` 可阻塞、可自带线程 | 由框架按时间序拉取，不得阻塞 |
| 输出时间戳 | 通常取环境当前时间 | 由上游时间戳 + `DelaySimulator` 推导 |

实践含义：**两种参数可以同时设置**，各模式自动忽略不相关的那个，业务代码因此可以完全复用。
`MainLogicCombination.hpp:61` 的 `logic` 节点就同时服务于
`MainLogic.cpp` 的 `run_real_or_virtual()` 与 `run_backtest()` 两条路径。

单遍迭代模式下 `DelaySimulator` 只影响输出时间戳，不影响计算顺序之外的任何东西——它不会让回测变慢，
只会让回测结果里的时间更贴近现实。

## 易错点

- **lift 形态与函数签名必须严格对应。** 返回 `std::optional<B>` 却调 `liftPure` 会得到
  `Action<A, std::optional<B>>`——编译通过，但下游收到的是 optional，语义全错。
  用 `GenericLift` 可避免这类错误。
- **`GenericLift` 对重载 / 模板化 `operator()` 不工作。** `boost::hana::curry` 产物、泛型 lambda
  都在此列，源码注释 `MainLogicCombination.hpp:205-207` 与 `245-246` 已明确记录。退回显式 lift。
- **`FireOnceOnly` 对 facility 无效。** `WithTimeData.hpp:59-61` 的注释写明
  "This only applies to actions, not to on-order facilities"。想让 facility 只响应一次需要别的手段。
- **`DelaySimulator` 的第一个参数是输入分支下标，不是输出下标。** 多输入节点要按 variant 的分支顺序
  分别给延迟。
- **enhanced 变体不能控制输出时间戳**，只是多收到一个输入时间戳。需要改输出时间或产出多个不同时间的
  数据，必须用 kleisli / kleisliMulti。
- **实时模式下不加 `SuggestThreaded` 的阻塞逻辑会拖住上游。** 节点默认在上游线程里同步执行。
  凡涉及 IO、锁、第三方阻塞 API，都应显式 `SuggestThreaded(true)`。
- **`passThroughAction<T>` 不接受 variant 与 `std::any`**（`RealTimeApp.hpp:1586-1588` 的 `enable_if`
  约束），多输入场合不能用它做恒等透传。
- **lift 只是创建节点，不等于加入图。** 还必须 `r.registerAction(...)` / `r.execute(...)`，
  或用 `DeclarativeGraph` 一步完成。未注册的节点在 `r.finalize()` 时不会被启动。
- **业务对象的生命周期要自己托住。** `MainLogicCombination.hpp:59` 用 `r.preservePointer(mainLogicPtr)`
  把 `shared_ptr` 交给 AppRunner 保管，因为 lift 进去的只是 `mainLogicPtr.get()` 裸指针。
- **`bunchedImporter` 的第二参数在两种模式下类型不同**（实时是 `NotUsed`，单遍迭代是 `BunchSplitLogic`），
  跨模式复用的代码要注意。

## 第三方依赖

- [Boost.Hana](https://www.boost.org/doc/libs/release/libs/hana/doc/html/index.html)：示例用
  `boost::hana::curry<2>` 把成员函数柯里化成一元可调用对象（`MainLogicCombination.hpp:5` 引入
  `<boost/hana/functional/curry.hpp>`）。注意其 `operator()` 重载会破坏 `GenericLift` 推导。
- 标准库 `<optional>` / `<variant>` / `<tuple>`：lift 形态矩阵直接建立在这三者之上。

## 相关章节

- [00-overview.md](00-overview.md) —— 数据流图总览
- [01-app-types.md](01-app-types.md) —— `RealTimeApp` 与单遍迭代 app 的完整对照
- [02-environments.md](02-environments.md) —— Environment 与 component
- [04-facilities.md](04-facilities.md) —— on-order facility 族，含 `liftPureOnOrderFacility` 等
- [05-app-runner.md](05-app-runner.md) —— `registerAction` / `execute` / `connect` / `finalize`
- [06-declarative-graph.md](06-declarative-graph.md) —— 用 `DeclarativeGraph` 声明节点与连边
- [07-time-and-data.md](07-time-and-data.md) —— `InnerData` / `WithTime` / `Data` / final 标记
- [08-runners-and-control.md](08-runners-and-control.md) —— 终止控制与多 runner
- [09-generated-pieces.md](09-generated-pieces.md) —— `*_Piece.hpp` 中 N 元版本的生成机制
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
