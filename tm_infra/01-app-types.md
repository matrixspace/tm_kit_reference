---
title: 四种执行模式对照
library: tm_infra
headers: [tm_kit/infra/RealTimeApp.hpp, tm_kit/infra/SinglePassIterationApp.hpp, tm_kit/infra/TopDownSinglePassIterationApp.hpp, tm_kit/infra/BasicWithTimeApp.hpp, tm_kit/infra/AppClassifier.hpp]
keywords: [RealTimeApp, SinglePassIterationApp, TopDownSinglePassIterationApp, BasicWithTimeApp, AppClassifier, 执行模型, 线程模型, 回测, backtest, PreserveInputRelativeOrder, AppSpecificMutex]
---

# 四种执行模式对照

## 用途

tm_infra 把"图长什么样"和"图怎么跑"分开了。同一份建图代码，换一个 app type（这里统称"执行模式"），就得到完全不同的执行语义：多线程实时、单线程回测、或者干脆不执行只做类型检查。

选型的决策点只有一个问题：**时间从哪来？**

- 时间来自挂钟 → `RealTimeApp`
- 时间来自数据本身的时间戳 → `SinglePassIterationApp` 或 `TopDownSinglePassIterationApp`
- 不关心时间，只想让编译器检查图的类型、顺便画出 Graphviz → `BasicWithTimeApp`

## 头文件与命名空间

```cpp
#include <tm_kit/infra/RealTimeApp.hpp>
#include <tm_kit/infra/SinglePassIterationApp.hpp>
#include <tm_kit/infra/TopDownSinglePassIterationApp.hpp>
#include <tm_kit/infra/BasicWithTimeApp.hpp>
#include <tm_kit/infra/AppClassifier.hpp>     // 四者都 include 了
```

命名空间 `dev::cd606::tm::infra`。

四者都是 `template <class StateT>`，`StateT` 就是你的 Environment 类型（见 [02-environments.md](02-environments.md)），所以惯例写法是：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:51
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

`M` 是习惯用的别名（取自 monad），`R` 是 `AppRunner`。

## 大对照表

| 维度 | RealTimeApp | SinglePassIterationApp | TopDownSinglePassIterationApp | BasicWithTimeApp |
|---|---|---|---|---|
| 定义位置 | `RealTimeApp.hpp:673` | `SinglePassIterationApp.hpp:58` | `TopDownSinglePassIterationApp.hpp:81` | `BasicWithTimeApp.hpp:15` |
| 文件行数 | 4005 | 3972 | 3570 | 970 |
| `PossiblyMultiThreaded` | `true`（`:679`） | `false`（`:63`） | `false`（`:93`） | `false`（`:20`） |
| `CannotHaveLoopEvenWithFacilities` | `false`（`:680`） | `false`（`:64`） | `false`（`:94`） | `false`（`:21`） |
| 时钟要求 | `PreserveInputRelativeOrder == false` | `== true`（模板约束，`:57`） | `== true`（模板约束，`:81`） | 无约束 |
| 时间推进 | 挂钟（或加速/对齐后的虚拟挂钟） | 数据时间戳，拉取式 | 数据时间戳，推送式 | 不推进，只走类型 |
| 执行驱动 | importer 自己的线程推送 | 从终端 exporter **反向拉取**（`poll()` / `next()`） | 从 importer **正向推送**，全局任务优先队列排序 | 不执行 |
| `finalize()` 行为 | 启动所有 `IExternalComponent` 后**立即返回**（`RealTimeApp.hpp:3402`） | 启动后在 `while (env->running())` 里轮询多路复用器直到 final 标记（`SinglePassIterationApp.hpp:3538`） | 启动后在 `while (env->running())` 里反复 `runOneStep(env)`（`TopDownSinglePassIterationApp.hpp:3132`） | 返回空 lambda，什么都不做（`BasicWithTimeApp.hpp:786`） |
| `finalize()` 返回后 | 图仍在后台跑，必须靠 `terminationController` 阻塞住 main | 图已跑完 | 图已跑完 | 无所谓 |
| `AppClassification` | `RealTime` | `SinglePass` | `TopDown` | `Empty` / `BasicWithTime` | 
| 互斥保护 | 节点内部有 `std::mutex` | 无（单线程，源码注释明示：`SinglePassIterationApp.hpp:55`） | 无 | 无 |
| `LiftParameters::suggestThreaded` | 生效（决定节点是否独占线程） | 忽略 | 忽略 | 忽略 |
| `LiftParameters::delaySimulator` | 忽略 | 生效（模拟逻辑耗时） | 生效 | 忽略 |
| 隐藏时间依赖 | 不涉及 | 不涉及 | 默认开启，可用 `NoHiddenTimeDependencyComponent` 关闭（`:84`） | 不涉及 |
| 典型用途 | 实时交易、实时风控、服务进程 | 回测（较早的实现） | **回测（推荐）** | CI 里的类型检查 + 出图 |

> **注意 `finalize()` 有两层，别混淆。** 上表说的是 **App 层**（`RealTimeApp::finalize()` 等，返回一个 `std::function<void(StateT *)>`）。业务代码里调的是 **`AppRunner::finalize()`**（`WithTimeData.hpp:2980`），它做的是：
>
> ```cpp
> void finalize() {
>     finalizeBegin();          // 校验连通性、环检测、finalizeEnvironment、touchup
>     m_.finalize()(env_);      // ← 调用 App 层，正是上表那一列
> }
> ```
>
> 所以"回测的 `finalize()` 会跑完整遍迭代"这件事发生在第二行——`AppRunner::finalize()` 本身不返回 lambda，它把 App 层返回的 lambda 立即用 `env_` 调用了。App 层的 `finalize()` 是 `M` 的成员，业务代码不直接调它。

`AppClassification` 的枚举值与别名见 `tm_infra/tm_kit/infra/AppClassifier.hpp:11`：`BasicWithTime` 是 `Empty` 的别名，`SinglePassIteration` 是 `SinglePass` 的别名，`TopDownSinglePass` 与 `TopDownSinglePassIteration` 都是 `TopDown` 的别名。

## 四者的共同 API 面

这是"业务代码可复用"的基础：四个 app type 都导出同一组类型别名，名字与含义完全一致。

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp.hpp:686（SinglePassIterationApp.hpp:67、
// TopDownSinglePassIterationApp.hpp:97、BasicWithTimeApp.hpp:24 处的代码逐字相同）
using TimePoint = typename StateT::TimePointType;
using Duration = decltype(TimePoint{} - TimePoint{});
using StateType = StateT;
using EnvironmentType = StateT;
template <class T>
using TimedDataType = WithTime<T, TimePoint>;
template <class T>
using Key = Key<T,StateT>;
template <class A, class B>
using KeyedData = KeyedData<A,B,StateT>;
```

源码注释解释了为什么这段代码在四个文件里重复而不是提取到公共头：模板继承有问题，直接复制反而更省事（`tm_infra/tm_kit/infra/RealTimeApp.hpp:684`）。

因此 `M::liftPure<...>`、`M::enhancedMaybe2<...>`、`M::liftPureOnOrderFacility<...>`、`M::Importer<T>`、`M::KeyedData<A,B>` 这类写法在四个模式下都成立——这就是业务代码能原样复用的原因。

## 最小可用示例：同一逻辑三种模式

锚点文件是 `tm_examples/simple_demo/plain_executables/MainLogic.cpp`，一个文件里三套跑法，业务逻辑 `MainLogicCombination` 完全复用。

**实时模式**（`run_real_or_virtual`）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40（已简化，省略部分组件）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::real_time_clock::ClockComponent>,
    transport::BoostUUIDComponent,
    transport::AllNetworkTransportComponents,
    transport::HeartbeatAndAlertComponent
>;
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

收尾（`:175`）：

```cpp
r.finalize();
infra::terminationController(infra::TerminateAtTimePoint { /* ... */ });
```

**回测模式**（`run_backtest`）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:191
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::FlagExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::top_down_single_pass_iteration_clock::ClockComponent<std::chrono::system_clock::time_point,true>,false>,
    basic::IntIDComponent<>
>;
using M = infra::TopDownSinglePassIterationApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

收尾（`:256`）：

```cpp
r.finalize();
infra::terminationController(infra::ImmediatelyTerminate {});
```

**类型检查模式**（`run_typecheck`）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:262
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::TrivialExitControlComponent,
    basic::TrivialBoostLoggingComponent,
    basic::real_time_clock::ClockComponent,
    basic::IntIDComponent<>
>;
using M = infra::BasicWithTimeApp<TheEnvironment>;
```

四种模式全部覆盖的例子在 `tm_examples/clock_logic_test/main.cpp`：`real_time_run`（`:23`）、`single_pass_iteration_run`（`:69`）、`top_down_single_pass_iteration_run`（`:92`）、`typecheck_run`（`:115`），四个函数共用同一个 `clock_logic_test_app::clockLogicMain(r, fileOutput)`。

## 各模式的执行模型

### RealTimeApp

多线程。每个节点可能跑在自己的线程上，由 `LiftParameters::suggestThreaded` 决定（`tm_infra/tm_kit/infra/WithTimeData.hpp:51`）。节点内部的 `ThreadedHandler` 负责排队与线程切换。

`finalize()` 只做一件事：遍历三组 `IExternalComponent` 调它们的 `start(env)`，然后返回（`tm_infra/tm_kit/infra/RealTimeApp.hpp:3402`）。图从此在后台自行运转，所以 main 函数必须用 `infra::terminationController(...)` 阻塞住，否则进程立刻退出。

`finalizeForInterleaving()` 返回的 stepper 恒为 `return false`，源码注释说明了原因：实时模式下动作都在各自线程上，stepper 无事可做（`tm_infra/tm_kit/infra/RealTimeApp.hpp:3429`）。

#### RealTimeApp 特有的两个环境标记与异常类型（`RealTimeApp.hpp:22`–`:31`）

```cpp
// :22 — 前向声明（定义在 SynchronousRunner.hpp）
template <class M> class SynchronousRunner;

// :26 — 空标记类：放进 Environment 后，各线程化节点会周期性把线程输入缓冲区的
//       当前长度以 LogLevel::Debug 打到日志里（见 :147、:244、:2486）
class OutputRealTimeThreadBufferSizeComponent {};

// :28 — RealTimeApp 抛出的异常类型
class RealTimeAppException : public std::runtime_error {
public:
    RealTimeAppException(std::string const &s) : std::runtime_error(s) {}
};
```

`OutputRealTimeThreadBufferSizeComponent` **不是一个可调参数**（类里没有任何字段）——它是**压测诊断开关**：实时图里某个节点处理不过来时，它的输入队列会堆积；打开这个标记后日志里能看到每个线程缓冲区的实时长度，用来定位瓶颈节点。只在排查性能问题时放进 Environment，平时不要放（高频 Debug 日志本身有开销）。

用法：`using TheEnvironment = infra::Environment<..., infra::OutputRealTimeThreadBufferSizeComponent, ...>;`

### SinglePassIterationApp

单线程，**拉取式**。源码顶部注释："Nothing in this monad is mutex protected because it is supposed to run single-threaded"（`tm_infra/tm_kit/infra/SinglePassIterationApp.hpp:55`）。

核心接口是 `poll()` 与 `next(Certificate<T> &&cert)`（`tm_infra/tm_kit/infra/SinglePassIterationApp.hpp:199`）。注释写明："The assumption is that next() will ONLY be called if poll() ..."（`:192`）——先 poll 确认有数据可取，再 next 真正取走。数据沿图**反向**被拉。

`finalize()` 把所有终端 exporter 汇聚成一个 `InputMultiplexer`，在 `while (env->running())` 里反复 poll/next，遇到 `finalFlag` 就 break（`tm_infra/tm_kit/infra/SinglePassIterationApp.hpp:3538`）。

### TopDownSinglePassIterationApp

单线程，**推送式**，回测的推荐选择。

执行核心是 `runOneStep(StateT *env)`（`tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:3052`）：先让各 importer 产数据进全局任务优先队列 `taskQueue_`（按时间排序），再从队首取出任务执行。`finalize()` 就是 `while (env->running()) { if (!runOneStep(env)) break; }`（`:3132`），`runOneStep` 在 importer 与任务队列都空时返回 false。

`runOneStep` 内部有两条分支，由 `UseExecutionStrategyThatAllowsForHiddenTimeDependency` 选择：

```cpp
// 来源：tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:84
static constexpr bool UseExecutionStrategyThatAllowsForHiddenTimeDependency
    = !std::is_convertible_v<
        StateT *
        , NoHiddenTimeDependencyComponent *
    >;
```

默认（Environment 里没放 `NoHiddenTimeDependencyComponent`）走允许隐藏时间依赖的策略：每步只从队列取**一个**任务，保证全局严格的时间顺序。关掉之后走另一条分支：一次把同一个 importer 产生的连续任务批量跑完，更快但不保证跨 importer 的严格排序。细节见 [02-environments.md](02-environments.md)。

### BasicWithTimeApp

不执行。`finalize()` 返回 `[](StateT *) {}`（`tm_infra/tm_kit/infra/BasicWithTimeApp.hpp:786`），`runStartedExporterSynchronously` 的参数全部未命名——函数体是空的（`:851`）。

价值在于：建图代码照样全套走一遍 C++ 类型检查，`r.writeGraphVizDescription(...)` 照样能出图。适合放进 CI，或者在改完一大段建图代码后先用它编一遍确认类型对得上，再去跑真正的回测。

## 编译期区分：AppClassifier

写通用代码（比如一个既要支持实时也要支持回测的工具库）时，需要在编译期知道当前是哪种模式。这就是 `AppClassifier.hpp`（整个文件只有 55 行）的作用：

```cpp
// 来源：tm_infra/tm_kit/infra/AppClassifier.hpp:45
template <class M>
constexpr AppClassification app_classification_v = AppClassifier<M>::TheClassification;

template <class M, class MutexType=std::mutex>
using AppSpecificMutex = std::conditional_t<app_classification_v<M> == AppClassification::RealTime, MutexType, bool>;

template <class M, class MutexType=std::mutex>
using AppSpecificLockGuard = std::conditional_t<app_classification_v<M> == AppClassification::RealTime, std::lock_guard<MutexType>, bool>;
```

`AppSpecificMutex` 这对别名是最实用的：在实时模式下它是真的 `std::mutex` + `std::lock_guard`，在单遍迭代模式下退化成 `bool`——零开销，而你的代码一个字不用改。写法上把成员声明成 `infra::AppSpecificMutex<M> mutex_;`，加锁处写 `infra::AppSpecificLockGuard<M> _(mutex_);` 即可。

注意 `bool _(mutex_)` 在非实时模式下是合法的 `bool` 构造，所以这招能编过。

## 实时 / 回测行为差异

本篇即是差异对照本身，上面的大对照表就是答案。额外几条在表格里不好表达的：

**时钟组件必须配套。** `SinglePassIterationApp` 与 `TopDownSinglePassIterationApp` 的模板声明带了 SFINAE 约束：

```cpp
// 来源：tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:81
template <class StateT, std::enable_if_t<StateT::PreserveInputRelativeOrder,int> = 0>
class TopDownSinglePassIterationApp {
```

`PreserveInputRelativeOrder` 由时钟组件提供：`basic/real_time_clock/ClockComponent.hpp:17` 是 `false`，`basic/single_pass_iteration_clock/ClockComponent.hpp:14` 与 `basic/empty_clock/ClockComponent.hpp:14` 是 `true`。所以**拿实时时钟配单遍迭代 app 会直接编不过**——这是好事，错误在编译期就被挡住了。反过来 `RealTimeApp` 没这个约束。

**`CheckTimeComponent` 的取值通常相反。** 看锚点文件：实时用 `CheckTimeComponent<false>`（`MainLogic.cpp:41`），回测用 `CheckTimeComponent<true>`（`:192`）。回测时数据应当严格按时间顺序，所以打开时间倒流检查；实时时数据来自网络，轻微的时间乱序是常态，开检查会丢数据。

**退出控制组件通常也不同。** 实时用 `TrivialExitControlComponent`（`running()` 恒 true，`exit()` 调 `std::exit`），回测用 `FlagExitControlComponent`（`running()` 读 atomic 标志）。原因：回测的 `finalize()` 里有 `while (env->running())` 主循环，需要一个能真的翻成 false 的标志才能优雅收尾。

## 易错点

- **实时模式忘了 `terminationController`**：`r.finalize()` 立即返回，main 跟着结束，进程退出，图一次都没跑。回测模式则相反——`finalize()` 返回时图已跑完，后面接 `ImmediatelyTerminate` 只是为了写法统一。
- **用错时钟**：编译期被挡（见上），但报错是 SFINAE 失败导致"没有匹配的模板"，不是人话。先检查时钟组件与 app type 是否配套。
- **在回测代码里手写 `std::mutex`**：能编过能跑，但白付开销，且暗示你对执行模型有误解。用 `AppSpecificMutex<M>`。
- **以为 `suggestThreaded` 在回测下也生效**：不生效。反过来 `delaySimulator` 只在单遍迭代模式下生效，实时模式忽略它。锚点示例
  `tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:66` 给 `logic` 配了 `DelaySimulator`，正是为了让回测时的因果时序更接近真实。
- **`SinglePassIterationApp` 与 `TopDownSinglePassIterationApp` 不可无脑互换**：两者的执行方向相反（拉取 vs 推送），对 importer 的实现要求也不同（前者要实现 `poll()`/`next()`，后者要实现 `next()` 往下推）。tm_basic 为两者提供了不同的时钟组件目录：`single_pass_iteration_clock/` 与 `top_down_single_pass_iteration_clock/`。
- **`BasicWithTimeApp` 跑出来没有任何输出是正常的**，不是 bug。

## 相关章节

- [00-overview.md](00-overview.md) —— tm_infra 总览与头文件地图
- [02-environments.md](02-environments.md) —— Environment 与 `NoHiddenTimeDependencyComponent`
- [05-app-runner.md](05-app-runner.md) —— `AppRunner::finalize()` 全流程
- [07-time-and-data.md](07-time-and-data.md) —— `LiftParameters`、`WithTime`、final 标记
- [08-runners-and-control.md](08-runners-and-control.md) —— `terminationController` 与 `SynchronousRunner`
- [09-generated-pieces.md](09-generated-pieces.md) —— 四个 app type 各自的生成片段
- [../tm_basic/01-clocks.md](../tm_basic/01-clocks.md) —— 四套时钟组件与 `PreserveInputRelativeOrder`
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
