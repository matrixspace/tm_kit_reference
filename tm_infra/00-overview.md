---
title: tm_infra 总览
library: tm_infra
headers: [tm_kit/infra/WithTimeData.hpp, tm_kit/infra/RealTimeApp.hpp, tm_kit/infra/SinglePassIterationApp.hpp, tm_kit/infra/TopDownSinglePassIterationApp.hpp, tm_kit/infra/BasicWithTimeApp.hpp, tm_kit/infra/Environments.hpp, tm_kit/infra/AppClassifier.hpp]
keywords: [tm_infra, 数据流图, data-flow graph, importer, exporter, action, on-order facility, std::variant, std::tuple, 头文件地图, AppRunner, TypeScript 绑定, C# 绑定]
---

# tm_infra 总览

## 用途

tm_infra 是 TM Kit 的最底层库，只做一件事：**定义数据流图（data-flow graph）的节点与图结构**。它不含任何第三方依赖（见仓库根 `CLAUDE.md`），不提供时钟、日志、序列化、传输——那些分别在 tm_basic 与 tm_transport 中。

它解决的核心问题是：让同一份业务逻辑代码，既能在多线程挂钟时间驱动的生产环境里跑（`RealTimeApp`），又能在单线程数据驱动的回测环境里跑（`SinglePassIterationApp` / `TopDownSinglePassIterationApp`），而业务逻辑本身一个字都不用改。

什么时候该直接用 tm_infra：你要定义节点、连接图、决定执行模式。什么时候不该：需要具体的时钟、文件导入、网络传输时，去找 tm_basic / tm_transport。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/WithTimeData.hpp>      // 数据包装 + AppRunner
#include <tm_kit/infra/RealTimeApp.hpp>       // 实时执行模式
#include <tm_kit/infra/Environments.hpp>      // Environment 组件混合
```

命名空间一律是 `dev::cd606::tm::infra`。示例代码普遍写 `using namespace dev::cd606::tm;` 然后用 `infra::` 前缀，见
`tm_examples/simple_demo/plain_executables/MainLogic.cpp:36`。

## 数据流图模型

程序被表达为一张图。节点分三类（术语见 [../GLOSSARY.md](../GLOSSARY.md)）：

| 节点类型 | 上游 | 下游 | 职责 |
|---|---|---|---|
| importer（导入节点） | 无 | 有 | 把图外数据引入图中；数据源通常不在图里体现 |
| exporter（导出节点） | 有 | 无 | 把数据送出图外，只产生副作用 |
| action（动作节点） | 有 | 有 | 变换数据 |

这三类节点在 `RealTimeApp` 中分别对应三个类型别名：

- `Importer` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:2129`
- `Exporter` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:2558`
- `Action` —— `tm_infra/tm_kit/infra/RealTimeApp.hpp:1146`

节点本身只是"持有者"（`OneWayHolder` / `TwoWayHolder`），真正的实现在它内部的 core 对象里。节点创建后要注册进 `AppRunner`，再用 `execute` / `connect` 一类调用把 source 接到 sink 上，这部分见 [05-app-runner.md](05-app-runner.md) 与 [06-declarative-graph.md](06-declarative-graph.md)。

## 设计决策：多输入用 variant，多输出用 tuple

这是 tm_infra 最有特色、也最容易让人困惑的一条决策。

**多输入建模为 `std::variant`。** 一个接受 N 个输入的 action 或 exporter，内部类型是 `Action<std::variant<A0,...,A(N-1)>, B>`。理由见 `tm_infra/README.md`：现实中这 N 路输入是在**不同时刻**各自到达的，任何一次实际处理都只面对其中一路，所以 variant 正是恰当的模型——而不是"同时拿到 N 个值"。

这直接解释了生成代码里那些数字后缀的 API：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:61
auto logic = M::template enhancedMaybe2<
        simple_demo::InputData
      , simple_demo::CalculateResult
    >(
        boost::hana::curry<2>(std::mem_fn(&MainLogic::runLogic))(mainLogicPtr.get())
      , dev::cd606::tm::infra::LiftParameters<std::chrono::system_clock::time_point>()
            /* ... DelaySimulator 略 ... */
    );
```

`enhancedMaybe2` 的 `2` 就是输入路数。被 lift 的函数实际签名是
`std::optional<CalculateCommand> runLogic(std::tuple<time_point, std::variant<InputData, CalculateResult>> &&)`
（`tm_examples/simple_demo/program_logic/MainLogic.hpp:24`）——参数里明明白白是一个 variant。数字后缀的完整规律见 [09-generated-pieces.md](09-generated-pieces.md)。

**抽象的泄漏。** 如果你**真的**想在两个节点之间传一个 `std::variant` 类型的业务数据，框架会把它当作"多输入"来解释，于是类型推导走偏。`tm_infra/README.md` 明确承认这一点，并给出唯一的办法：**把 variant 包进一层外部数据结构**（struct 或别的容器）再传。这是整套抽象里唯一已知的泄漏点，作者的评价是"希望这不是个大问题"。

**多输出建模为 `std::tuple` 或 struct。** 多路输出的情形不同：它们一般是**同时**产生的，所以 tuple / struct 完全够用，不需要 variant。对于"同类型的多个输出"，框架还提供了让逻辑产出 `std::vector`、下游逐条收取的 multi 系列 lift（`liftMulti` / `liftMultiN`）。当然你也可以不用这些设施，直接让节点生产和消费 `std::vector`。

要把一个 tuple 输出分发到多个下游，用 `dispatchTupleAction`：

```cpp
// 来源：tm_examples/common_flow_util_tests/Tuple2VariantTest.cpp:26
infra::DeclarativeGraph<R>("", {
    {"importer", M::constFirstPushImporter<std::tuple<std::string, int>>({"abc", 10})}
    , {"t2v", M::dispatchTupleAction<std::string,int>()}
    /* ... printer1 / printer2 定义略 ... */
    , {"importer", "t2v"}
    , {"t2v", 0, "printer1"}
    , {"t2v", 1, "printer2"}
})(r);
```

## facility 四变体

除了三类通用节点，tm_infra 还提供一族专用节点：on-order facility（按单设施）。它接受**带 tag 的**输入（tag 不能是 variant），对每个输入产出零个、一个或多个同 tag 的输出。名字来自生产车间的比喻：对不可互换的生产订单逐单响应。

facility 用一套与 action 不同的连接语法接入图，这使得**图中可以成环**——只要每个环里至少含一个 facility。

四个变体是围绕"facility 还需要别的输入/输出"这一需求做的捆绑：

| 变体 | 组成 | 定义位置（RealTimeApp 中） |
|---|---|---|
| `OnOrderFacility<A,B>` | 纯 facility | `tm_infra/tm_kit/infra/RealTimeApp.hpp:1797` |
| `LocalOnOrderFacility<A,B,C>` | facility + exporter | `tm_infra/tm_kit/infra/RealTimeApp.hpp:2822` |
| `OnOrderFacilityWithExternalEffects<A,B,C>` | facility + importer | `tm_infra/tm_kit/infra/RealTimeApp.hpp:2923` |
| `VIEOnOrderFacility<A,B,C,D>` | facility + importer + exporter | `tm_infra/tm_kit/infra/RealTimeApp.hpp:3024` |

要点：捆绑的几个指针**可以指向同一个对象**（该对象同时实现多个接口），这正是 facility 拿到辅助数据的途径——框架不追求节点纯函数化，facility 持有指针与别的节点共享状态是被允许的。`VIE` 取自 "variable interest entity"（可变利益实体），延续生产/贸易的比喻。

此外还有 `FacilitioidConnector`（`tm_infra/tm_kit/infra/WithTimeData.hpp:761`）——一个"可当作 facility 使用"的连接器抽象，让本地 facility 与远程 facility 在调用处长得一样。细节见 [04-facilities.md](04-facilities.md)。

实际用法示例（lift 一个普通函数成 facility）：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:106
cfgFacility = M::template liftPureOnOrderFacility<
    std::tuple<std::string, simple_demo::ConfigureCommandPOCO>
>(
    boost::hana::curry<2>(std::mem_fn(&MainLogic::configure))(mainLogicPtr.get())
);
r.registerOnOrderFacility("cfgFacility", cfgFacility);
r.markStateSharing(cfgFacility, logic, "enabled");
```

注意 `markStateSharing`：facility 与 action 共享了同一个 `MainLogic` 对象，这件事必须显式告知 `AppRunner`，否则图的时序校验与可视化都不知道这条隐含依赖。

## 头文件地图

`tm_infra/tm_kit/infra/` 下共 **78 个 `.hpp`**，分成两堆：

- **26 个手写头文件**
- **52 个机器生成的代码片段**（50 个 `*_Piece.hpp` + 2 个 `*_ClassPiece.hpp`），合计约 14 万行

生成文件不是独立头文件，而是被 `#include` 到类体**内部**的片段，不要直接阅读，规律见 [09-generated-pieces.md](09-generated-pieces.md)。

26 个手写头文件按职责分六类：

**1. 执行模式（app type）—— 四选一，决定整个程序的执行语义**

| 文件 | 行数 | 说明 |
|---|---|---|
| `RealTimeApp.hpp` | 4005 | 实时、多线程 |
| `SinglePassIterationApp.hpp` | 3972 | 单遍迭代，拉取式 |
| `TopDownSinglePassIterationApp.hpp` | 3570 | 单遍迭代，推送式（回测首选） |
| `BasicWithTimeApp.hpp` | 970 | 只做类型检查与图可视化，不真正执行 |
| `AppClassifier.hpp` | 55 | 编译期区分上面四者，见 [01-app-types.md](01-app-types.md) |

**2. 数据与图核心**

- `WithTimeData.hpp`（4316 行）—— 全库最核心的手写文件：`WithTime`、`InnerData`、`Key`/`KeyedData`、`LiftParameters`、以及 `AppRunner` 本体。见 [07-time-and-data.md](07-time-and-data.md) 与 [05-app-runner.md](05-app-runner.md)。
- `VersionedData.hpp`（333 行）—— 带版本的数据与 `VersionChecker`。
- `TupleVariantHelper.hpp`（118 行）—— tuple/variant 互转的编译期辅助。
- `ChronoUtils.hpp`（239 行）—— 时间点与字符串互转。

**3. lift（提升）工具**

- `KleisliUtils.hpp`（1555 行）—— kleisli 形态的组合工具。
- `KleisliSequence.hpp`（25 行）—— kleisli 串联。
- `GenericLift.hpp`（532 行）—— 从函数签名自动推断该用 pure/maybe/multi 哪种 lift。**注意**：`GenericLift` 对 `boost::hana::curry` 产生的对象不工作，因为后者的 `operator()` 是重载的；源码注释见 `tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:205`。

详见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md)。

**4. 图的声明式构造与检查**

- `DeclarativeGraph.hpp`（510 行）—— 用初始化列表一次性描述整张图，见 [06-declarative-graph.md](06-declarative-graph.md)。
- `AutoConnectionSubGraph.hpp`（175 行）
- `NodeClassifier.hpp`（378 行）
- `GraphCheckComponents.hpp`（13 行）—— 放进 Environment 以开关图校验，如 `CheckActionChains`、`DontCheckConnections`。

**5. 运行与控制**

- `SynchronousRunner.hpp`（514 行）—— 同步调用图的一部分，不走 `AppRunner::finalize()`。
- `TerminationController.hpp`（63 行）—— `RunForever` / `ImmediatelyTerminate` / `TerminateAtTimePoint` / `TerminateAfterDuration`。
- `StoppableProducer.hpp`（109 行）、`ControllableNode.hpp`（15 行）、`ObservableNode.hpp`（15 行）

见 [08-runners-and-control.md](08-runners-and-control.md)。

**6. 环境组件**

- `Environments.hpp`（113 行）—— `Environment<Components...>` 本体与几个内置组件，见 [02-environments.md](02-environments.md)。
- `LogLevel.hpp`（79 行）
- `TraceNodesComponent.hpp`（215 行）
- `GraphStructureBasedResourceHolderComponent.hpp`（139 行）
- `PidUtil.hpp`（10 行）

## 实时 / 回测行为差异

tm_infra 本身不定义时间从哪来——那是 Environment 里时钟组件的事。库层面提供的是"同一业务代码换一个 app type 就换一套执行语义"这个机制。锚点是
`tm_examples/simple_demo/plain_executables/MainLogic.cpp`：

- `run_real_or_virtual()`（`:39`）用 `infra::RealTimeApp<TheEnvironment>`（`:51`）
- `run_backtest()`（`:190`）用 `infra::TopDownSinglePassIterationApp<TheEnvironment>`（`:197`）
- `run_typecheck()`（`:261`）用 `infra::BasicWithTimeApp<TheEnvironment>`（`:269`）

三者共用同一个 `MainLogicCombination`。各模式的执行模型对照见 [01-app-types.md](01-app-types.md)。

## 易错点

- **真要传 `std::variant`**：必须包一层外部结构，否则会被当作多输入解释。这是已知的抽象泄漏。
- **共享状态要显式声明**：节点间共享对象（facility 与 action 共用一个逻辑对象）必须调 `r.markStateSharing(...)`，见上文示例。
- **编译错误很长**：README 自己就提醒了——所有类型检查都在 C++ 类型系统里做，一处类型不匹配会产出极长的报错。先看报错最顶上那几行里的 `Action<std::variant<...>, ...>`，对照输入路数是否与你用的 `liftXxxN` 的 N 一致。
- **图成环只能靠 facility**：普通 action 构成的环不被允许；环里必须至少有一个 on-order facility。

## 第三方依赖

tm_infra **无第三方依赖**，这是设计约束（`tm_infra/README.md`：No third party library is required）。
依赖要求只有编译器与构建工具：GCC >= 9.3.1 / clang >= 10.0.1 / MSVC Build Tools 2019，加 meson。C++17。

示例代码里出现的 `boost::hana::curry` 来自 tm_examples，不是 tm_infra 的依赖。

## TypeScript 与 C# 绑定

除 C++ 之外，tm_infra 还附带两套"小份"的同构实现，定位是**让非 C++ 侧的代码能用相似的写法与 C++ 侧交互**，而不是提供完整的框架能力。

**TypeScript** —— `tm_infra/node_lib/`

- 包名 `@dev_cd606/tm_infra`，入口 `node_lib/src/index.ts`，类型在 `node_lib/src/types.ts`
- `node_lib/package.json` 自述为 "Pure Node.js implementation of tm_infra (currently only partial functionalities of RealTimeApp)"——**只有 RealTimeApp 的部分功能**，没有单遍迭代模式
- 要求 Node >= 18；依赖 `uuid`、`stream`、`process`

**C#** —— `tm_infra/TMInfraDotNet/`

- 文件为 `BasicDataTypes.cs`、`KleisliUtils.cs`、`RealTimeApp.cs`、`RealTimeAppRunner.cs`
- 命名空间 `Dev.CD606.TM.Infra.RealTimeApp`
- 同样只覆盖 RealTimeApp 一侧，功能定位与 TypeScript 版对等（`tm_infra/README.md`："Some C# codes, similar in functionalities to the Typescript codes, are also provided"）

两者的 API 本篇不展开。要判断能不能用：如果你的需求是"在 Node 或 .NET 里接收/发送 TM Kit 的实时数据流"，可以考虑；如果需要回测、facility 的完整四变体、或图校验，就只有 C++ 侧有。

## 相关章节

- [01-app-types.md](01-app-types.md) —— 四种执行模式的对照
- [02-environments.md](02-environments.md) —— Environment 组件混合模型
- [03-nodes-and-lifting.md](03-nodes-and-lifting.md) —— 节点构造与各种 lift
- [04-facilities.md](04-facilities.md) —— facility 四变体详解
- [05-app-runner.md](05-app-runner.md) —— AppRunner 的注册、连接、校验
- [06-declarative-graph.md](06-declarative-graph.md) —— DeclarativeGraph
- [07-time-and-data.md](07-time-and-data.md) —— 时间与数据包装
- [08-runners-and-control.md](08-runners-and-control.md) —— 运行与终止控制
- [09-generated-pieces.md](09-generated-pieces.md) —— 生成代码的规律与数字后缀
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
- [../tm_basic/01-clocks.md](../tm_basic/01-clocks.md) —— 时钟组件
