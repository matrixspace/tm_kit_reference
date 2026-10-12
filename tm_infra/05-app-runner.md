---
title: AppRunner —— 组图中枢
library: tm_infra
headers: [tm_kit/infra/WithTimeData.hpp, tm_kit/infra/WithTimeData_VariantSink_Piece.hpp, tm_kit/infra/WithTimeData_ConnectN_Piece.hpp, tm_kit/infra/WithTimeData_ConnectN_ClassPiece.hpp, tm_kit/infra/WithTimeData_VariantSink_ClassPiece.hpp]
keywords: [AppRunner, app runner, 组图, Source, Sink, clone, registerAction, registerImporter, registerExporter, connect, connectAny, finalize, writeGraphVizDescription, detectCycle, markStateSharing, preservePointer, addTouchup, touchup, Sourceoid, Sinkoid, FacilitioidConnector, setMaxOutputConnectivity, connectTypedSinkToAllNodes, connectAnySinkToAllImporters, connectTypedSinkToAllImporters, connectSourceToAllSinks, connectSourceToAllUnusedSinks, connectSourceoidToAllSinks, connectSourceoidToAllUnusedSinks]
---

# AppRunner —— 组图中枢

## 用途

`AppRunner<App>` 是把一堆节点对象组装成一张数据流图的中枢。它做四件事：给节点登记名字、把 source 接到 sink、在 `finalize()` 时校验整张图、以及按需输出 Graphviz 描述。业务逻辑写出来的 importer / action / exporter / facility 本身只是函数对象，不知道彼此的存在；是 `AppRunner` 把它们连起来并交给 `App` 执行。

定义在 `tm_infra/tm_kit/infra/WithTimeData.hpp:629`。同一份业务组图代码换一个 `App` 模板参数即可在实时与回测模式间切换，这是 TM Kit 的核心设计——见 [01-app-types.md](01-app-types.md)。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/WithTimeData.hpp>
```

命名空间 `dev::cd606::tm::infra`。模板参数 `App` 取 `RealTimeApp<Env>`、`TopDownSinglePassIterationApp<Env>`、`SinglePassIterationApp<Env>` 或 `BasicWithTimeApp<Env>`。

典型别名约定（全套 example 都这么写）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:51
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

## 核心类型与签名

### 环境与 App 相关别名

`WithTimeData.hpp:630` 起：

```cpp
using AppType = App;
using EnvironmentType = typename App::StateType;
using StateT = typename App::StateType;
```

`EnvironmentType` 与 `StateT` 是同一个东西，两个名字都在库内被使用。

### 节点类型别名体系

`WithTimeData.hpp:633`–`659`，每种节点都有裸类型和 `shared_ptr` 版本两个别名：

| 别名 | 模板参数 | 含义 |
|---|---|---|
| `Action<A,B>` / `ActionPtr<A,B>` | 输入 A、输出 B | action 节点 |
| `Importer<T>` / `ImporterPtr<T>` | 产出 T | importer 节点 |
| `Exporter<T>` / `ExporterPtr<T>` | 消费 T | exporter 节点 |
| `OnOrderFacility<A,B>` / `...Ptr` | 请求 A、响应 B | on-order facility |
| `LocalOnOrderFacility<A,B,C>` / `...Ptr` | 另加辅助输入 C | facility + exporter |
| `OnOrderFacilityWithExternalEffects<A,B,C>` / `...Ptr` | 另加额外输出 C | facility + importer |
| `VIEOnOrderFacility<A,B,C,D>` / `...Ptr` | 另加输入 C、输出 D | facility + importer + exporter |

四族 facility 的语义见 [04-facilities.md](04-facilities.md)。Ptr 版本一律是 `std::shared_ptr<...>`——**AppRunner 的全部 API 都收 `shared_ptr`，节点的所有权由 runner 共同持有**，所以局部变量离开作用域不会析构节点。

### Source<T> 与 Sink<T>

这两个是连接用的句柄，不是节点本身。

`Source<T>`（`WithTimeData.hpp:664`）：

```cpp
// WithTimeData.hpp:692, :695, :702
Source<T> clone() const;
typename App::template Source<T>&& theSource() &&;   // 注意 && 限定
std::string registeredNodeName() const;
```

`Sink<T>`（`WithTimeData.hpp:707`）只有一个公开方法 `registeredNodeName()`（`:717`），其余成员私有、只供 `AppRunner` 访问。

**`Source` 可拷贝可 clone，`Sink` 只能当值传。** `Source` 的拷贝构造与拷贝赋值在内部对底层 source 调用 `clone()`，所以 `Source` 的副本是语义上独立的新输出端。

### Sourceoid / Sinkoid / FacilitioidConnector

`WithTimeData.hpp:746` 起定义了一组"延迟连接"的函数类型，用于让组图函数接受"还不知道从哪来的输入"：

```cpp
template <class A> using Sourceoid = std::function<void(AppRunner &, typename SinkMatch<A>::TheType const &)>;   // :746
using SingleSourceoidForAny = std::function<void(AppRunner &, Sink<std::any> const &)>;                           // :747
template <class A> using SourceoidForAny = ...;                                                                    // :749
template <class A> using Sinkoid = std::function<void(AppRunner &, Source<A> &&)>;                                 // :751
template <class A> using ConvertibleToSourceoid = std::variant<Source<A>, Sourceoid<A>, std::optional<Source<A>>>; // :754
template <class A, class B> using FacilitioidConnector = ...;                                                      // :761
```

`FacilitioidConnector<A,B>` 是整套文档里出现频率最高的抽象——它让"向某个 facility 下单"这件事与"facility 到底是本地的还是远程的"解耦。`MainLogic.cpp:101` 用它同时容纳远程 facility 与本地 mock facility：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:101-116（已简化）
R::FacilitioidConnector<CalculateCommand,CalculateResult> calc;
if (isReal) {
    calc = transport::MultiTransportRemoteFacilityManagingUtils<R>
        ::setupOneNonDistinguishedRemoteFacility<CalculateCommand, CalculateResult>(
            r, heartbeatSource.clone(), std::regex("simple_demo plain Calculator"), "calculator facility"
        ).facility;
} else {
    calc = &(MockCalculatorCombination<R, basic::real_time_clock::ClockOnOrderFacility<TheEnvironment>>::service);
}
```

详见 [04-facilities.md](04-facilities.md)。

### 构造与基本查询

```cpp
AppRunner(StateT *env);                        // WithTimeData.hpp:1460
template <class T> AppRunner(T t, StateT *env); // :1462
StateT *environment() const;                   // :1469
template <class X> void moveToAnotherRunner(X &x); // :1473
```

`AppRunner` 不可拷贝，可移动。`moveToAnotherRunner` 把内部 App 对象交给另一个持有者（调用对方的 `takeOver(env, std::move(m))`），用于把已组好的图移交给 `SynchronousRunner` 这类对象——见 [08-runners-and-control.md](08-runners-and-control.md)。

所有抛出的异常都是 `AppRunner::AppRunnerException`（`WithTimeData.hpp:1456`，派生自 `std::runtime_error`）。

## 注册 API

七个 `register*` 方法，每个都有 `(ptr, name)` 与 `(name, ptr)` 两种参数序重载：

| 方法 | 参数序 1 | 参数序 2 |
|---|---|---|
| `registerAction` | `:1478` | `:1482` |
| `registerImporter` | `:1486` | `:1490` |
| `registerExporter` | `:1494` | `:1498` |
| `registerOnOrderFacility` | `:1502` | `:1506` |
| `registerLocalOnOrderFacility` | `:1510` | `:1517` |
| `registerOnOrderFacilityWithExternalEffects` | `:1524` | `:1531` |
| `registerVIEOnOrderFacility` | `:1538` | `:1546` |

两种参数序完全等价，选哪种看哪边读起来顺：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:165, :220-222
r.registerAction("extractEnabled", extractEnabled);
r.registerImporter("importer", importer);
r.registerAction("parser", parser);
```

名字必须全图唯一，重复注册同一指针用不同名字会抛 `AppRunnerException`。名字里的 `.` 会被 `writeGraphVizDescription` 当作子图层级分隔符，也被 `GraphStructureBasedResourceHolderComponent` 用作资源作用域前缀。

## 取句柄 API

这些方法既取句柄又顺手注册（给了 `name` 的重载会先注册，没给的重载要求节点已注册）：

| 方法 | 带 name | 不带 name | 返回 |
|---|---|---|---|
| `importerAsSource` | `:1554` | `:1562` | `Source<DataType>` |
| `importItem` | `:1571` | `:1575` | 同上（`importerAsSource` 的别名） |
| `actionAsSource` | `:1579` | `:1587` | `Source<OutputType>` |
| `exporterAsSink` | `:1702` | `:1710` | `Sink<DataType>` |
| `actionAsSink` | `:1719` | `:1727` | `Sink<InputType>` |
| `localFacilityAsSink` | `:1736` | `:1751` | `Sink<DataType>` |
| `vieFacilityAsSink` | `:1764` | `:1781` | `Sink<ExtraInputType>` |
| `facilityWithExternalEffectsAsSource` | `:1795` | `:1810` | `Source<DataType>` |
| `vieFacilityAsSource` | `:1823` | `:1840` | `Source<ExtraOutputType>` |

### 带数字后缀的变体：actionAsSink_N_K

当 action 的输入是 `std::variant<A0,...,A(N-1)>`（多输入节点的建模方式，见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md)），`actionAsSink` 无法表达"接到第几个输入上"。此时用 `actionAsSink_N_K`：**N 是 variant 的分支总数，K 是要连接的分支下标（0 起）**。

签名生成在 `tm_infra/tm_kit/infra/WithTimeData_VariantSink_Piece.hpp:2` 起，例如：

```cpp
// tm_infra/tm_kit/infra/WithTimeData_VariantSink_Piece.hpp:1-8
template <class A0, class A1, class B>
Sink<A0> actionAsSink_2_0(std::string const &name, ActionPtr<std::variant<A0,A1>,B> const &action);
```

返回的 `Sink` 其 `pos` 字段就是 K，`finalize()` 会逐个 position 检查连通性。真实用例：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:140
return MainLogicOutput<R> {
    r.actionAsSink_2_0(logic)    // logic 输入是 variant<InputData, CalculateResult>，取第 0 路
};
```

这里 `logic` 由 `M::enhancedMaybe2<InputData, CalculateResult>` 提升而来（同文件 `:61`），所以第 0 路是 `InputData`、第 1 路是 `CalculateResult`。第 1 路在同文件 `:92` 由 `r.execute(logic, ...)` 隐式接上。

`connect_N_K` / `connectAny_N_K` 同理，生成在 `WithTimeData_ConnectN_Piece.hpp`，类形式封装在 `WithTimeData_ConnectN_ClassPiece.hpp:1`（`Connect<N,K>::call` / `ConnectAny<N,K>::call`），供模板代码按编译期索引分发。上限由 `WithTimeData.hpp:46` 的 `MAX_FAN_IN_BRANCH_COUNT = 20` 决定。

## 执行与连接 API

### execute / executeAny

```cpp
// WithTimeData.hpp:1596, :1607
template <class Action>
Source<OutputType> execute(std::string const &name, std::shared_ptr<Action> const &f, Source<InputType> &&x);
template <class Action>
Source<OutputType> execute(std::shared_ptr<Action> const &f, Source<InputType> &&x);

// WithTimeData.hpp:1627, :1646
template <class Action, class A>
Source<OutputType> executeAny(std::string const &name, std::shared_ptr<Action> const &f, Source<A> &&x);
```

`execute` 是最常用的组图原语：注册 action（若给了 name）、把 `x` 接到它的输入、返回它的输出 source。可以嵌套，读起来就是数据流方向：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:224
auto dataInput = r.execute(removeTopic, r.execute(parser, r.importItem(importer)));
```

`executeAny` 用于输入类型是 `std::any` 的 action（通用监控/落盘节点），它允许把任意类型的 source 接进去。

### exportItem / exportAnyItem / feedItemToLocalFacility

```cpp
void exportItem(std::string const &name, ExporterPtr, Source<DataType> &&);   // :1660
void exportItem(ExporterPtr, Source<DataType> &&);                            // :1665
void exportAnyItem(std::string const &name, ExporterPtr<std::any>, Source<T> &&); // :1677
void exportItem(ExporterPtr<std::any>, Source<T> &&);                         // :1689（any 重载）
void feedItemToLocalFacility(std::string const &name, FacPtr, Source<DataType> &&); // :1693
void feedItemToLocalFacility(FacPtr, Source<DataType> &&);                    // :1697
```

这些都是 `connect` / `connectAny` 的便利封装（看实现一目了然：`:1662` 就是 `connect(std::move(x), exporterAsSink<Exp>(name, f))`）。

### connect / connectAny

```cpp
template <class T> void connect(Source<T> &&source, Sink<T> const &sink);          // :2207
template <class T> void connectAny(Source<T> &&source, Sink<std::any> const &sink); // :2221
```

最底层的连边操作。`source` 按右值传入（会被消耗），`sink` 按 const 引用（可重复使用，受 max input connectivity 限制）。

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:144, :166, :173
r.connect(std::move(inputDataSource), mainLogicOutput.dataSink);
r.connect(heartbeatForPubSource.clone(), r.actionAsSink(extractEnabled));
r.connect(r.actionAsSource(extractEnabled), enabledPubSink);
```

`connectAny` 只接受非 variant 的 `T`（`WithTimeData.hpp:2220` 的 `enable_if`），用于把具体类型的流送进 `std::any` 的通用 sink。

## 批量连接：全局监控与落盘

这一族共 **八个**方法，分两组、互为对偶：**sink 侧**把一个 sink 接到全图所有输出端，**source 侧**把一个 source 接到全图所有输入端。

### sink 侧（收全图数据）

```cpp
void connectAnySinkToAllNodes(Sink<std::any> const &sink);        // :2290
void connectAnySinkToAllImporters(Sink<std::any> const &sink);    // :2302
template <class T> void connectTypedSinkToAllNodes(Sink<T> const &sink);      // :2315
template <class T> void connectTypedSinkToAllImporters(Sink<T> const &sink);  // :2332
```

- `...AllNodes` 接所有 importer、action、带外部效应的 facility、VIE facility 的输出（这些节点在注册时把自己的 sourceoid 登记进 `sourceoidsForAny_` / `typedSourceoids_`，见 `:1086`、`:1125`、`:1267`、`:1307`）。
- `...AllImporters` 只接 importer 和"importer 性质"的 facility（登记进 `sourceoidsForAnyFromImporter_`，见 `:1126`、`:1268`、`:1308`）。
- `Any` 版本要求 sink 类型是 `Sink<std::any>`，能抓住全图所有类型；`Typed` 版本只抓类型恰为 `T` 的输出。

### source 侧（向全图注入数据）

```cpp
template <class A> void connectSourceToAllSinks(Source<A> &&source);           // :2411
template <class A> void connectSourceToAllUnusedSinks(Source<A> &&source);     // :2415
template <class A> void connectSourceoidToAllSinks(Sourceoid<A> const &source);        // :2403
template <class A> void connectSourceoidToAllUnusedSinks(Sourceoid<A> const &source);  // :2407

// 内部实现（Sourceoid 版本走这几条）
void connectSingleSourceoidToAllSinks_internal(Sourceoid<T> const &source, bool unusedOnly);       // :2350
void connectMultiSourceoidToAllSinks_internal(Sourceoid<TheVariant> const &source, bool unusedOnly); // :2387
void connectMultiSourceoidToAllSinks_internal_helper(Sourceoid<TheVariant> const &source, bool unusedOnly); // :2367
```

**`...UnusedSinks` 与不带 `Unused` 的区别**：不带 `Unused` 的版本接到**所有**匹配的 sink 上（包括已经连过的）；`...UnusedSinks` 只接**尚未连接**的 sink。后者是"填洞"——组完图后把剩下没接的输入一口气接上，避免 `finalize()` 报"某个输入没连"。

`Sourceoid` 与 `Source` 版本的差别见上文 §Sourceoid / Sinkoid：`Source` 是已实体化的输出端（会被 `std::move` 消耗），`Sourceoid` 是"接到某个 sink 时才真正连线"的延迟函数。

**典型用法**：source 侧接一个测试数据或回放 importer，一次性喂给图里所有下游；sink 侧接一个录制 exporter 落盘全部行情与中间信号，之后在单遍迭代模式下回放。

注意这八个方法**不是立即执行**，而是通过 `addTouchup` 延迟到 finalize 阶段（看 `:2291` 的实现），因为"所有节点"必须等到图组完才算数。

`tm_transport` 的 `multi_transport_touchups::ListenerTouchup` 就是用 `connectSourceToAllUnusedSinks` 实现"把一路新订阅的广播喂给所有还没接的消费者"——见 [tm_transport/05-heartbeat-and-alert.md](../tm_transport/05-heartbeat-and-alert.md)。

**示例代码库中暂无直接用例**，请以上述签名为准。

## 连通度约束与状态共享

### 连通度

```cpp
void setMaxOutputConnectivity(Source<T> &&source, size_t n);              // :2238
void setMaxOutputConnectivity(std::string const &source, size_t n);       // :2242
void setMaxOutputConnectivity(std::shared_ptr<F> const &source, size_t n); // :2247
void setMaxInputConnectivity(Sink<T> const &sink, size_t n);              // :2253
void setMaxInputConnectivity(std::string const &sink, int pos, size_t n); // :2257
void setMaxInputConnectivity(std::shared_ptr<F> const &sink, int pos, size_t n); // :2262
void restrictFacilityOutputConnectionByDefault();                         // :2267
void dontRestrictFacilityOutputConnectionByDefault();                      // :2271
```

**facility 输出默认限制为单连接**：构造函数把 `restrictFacilityOutputConnectionByDefault_` 初始化为 `true`（`:1460`），于是每个 facility 注册时自动执行 `setMaxOutputConnectivity_(name, 1)`（`:1194`、`:1226`、`:1263`、`:1304`）。要让一个 facility 服务多个调用方必须显式放宽：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:113
r.setMaxOutputConnectivity(cfgFacility, input.configWrappers.size());
```

这段代码让同一个配置 facility 同时被 RabbitMQ 和 JSON REST 两个 wrapper 包装（`MainLogic.cpp:120-131` 给了两个 wrapper），少了这一行 `finalize()` 会报超出连通度上限。

### markStateSharing

```cpp
template <class A, class B>
void markStateSharing(std::shared_ptr<A> const &item1, std::shared_ptr<B> const &item2,
                      std::string const &sharedStateName="");   // :2999
```

声明两个节点共享内部状态。图上这两个节点之间没有连边，但它们读写同一份数据——这个事实对读图的人至关重要，`markStateSharing` 把它登记到 `stateSharingRecords_` 并在 Graphviz 输出里画出来。两个参数是同一个节点时抛 `AppRunnerException`（`:3002`）。

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:112, :126, :136
r.markStateSharing(cfgFacility, logic, "enabled");
r.markStateSharing(queryFacility, logic, "outstanding_cmds");
r.markStateSharing(clearCommandsFacility, logic, "outstanding_cmds");
```

这三行的背景是：`logic`、`cfgFacility`、`queryFacility`、`clearCommandsFacility` 全部从同一个 `std::shared_ptr<MainLogic>` 上的成员函数提升而来（同文件 `:65`、`:109`、`:122`、`:132` 都是 `std::mem_fn(&MainLogic::...)` 绑到 `mainLogicPtr.get()`），所以它们天然共享 `MainLogic` 的成员变量。

### preservePointer

```cpp
template <class T> void preservePointer(std::shared_ptr<T> const &ptr);   // :2993
```

把任意 `shared_ptr` 存进 runner 的 `otherPreservedPtrs_`，延长其生命周期到 runner 析构。用在业务对象本身不是节点、但被多个节点以裸指针捕获的场景：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:53-59
auto mainLogicPtr = std::make_shared<MainLogic>(...);
r.preservePointer(mainLogicPtr);
```

`mainLogicPtr` 是组图函数的局部变量，函数返回即析构；但后续各节点捕获的是 `mainLogicPtr.get()` 裸指针。没有这一行就是悬垂指针——**这是组图时最容易写出的 use-after-free**。

## addTouchup：延迟图修补

```cpp
void addTouchup(std::function<void(AppRunner &)> const &touchup);   // :2282
```

注册一个回调，在 touchup 阶段（`finalize()` 或 `writeGraphVizDescription()` 内部的 `doTouchups()`）执行，此时整张图已组完。touchup 只执行一次（`touchupDone_` 标记），之后再调 `addTouchup` 抛 `AppRunnerException`（`:2284`）。

批量连接的四个方法就是基于它实现的。自己用 `addTouchup` 的场合是"需要看到全图才能决定怎么连"的逻辑。

## 生命周期与校验

```cpp
void finalize();                                     // :2980
std::function<bool()> finalizeForInterleaving();     // :2984
```

`finalize()` 等于 `finalizeBegin()` 再加 `m_.finalize()(env_)`，后者才真正启动图。`finalizeBegin()`（`:2857`，私有）按顺序做：

1. 若 Environment 带 `GraphStructureBasedResourceHolderComponent`，把节点名注册进去并 `resolveAllResources()`（`:2858`–`:2863`）。
2. `env_->EnvironmentType::finalizeEnvironment()`（`:2864`）。
3. `doTouchups()`（`:2865`）。
4. 除非 Environment 带 `graph_check_components::DontCheckConnections`，遍历每个节点的每个输入位置，未连接就抛 `AppRunnerException`，超出 input 连通度上限也抛（`:2869`–`:2890`）。
5. 环检测：`detectCycle(false)` 再 `detectCycle(true)`（`:2934`、`:2940`）。
6. 若带 `graph_check_components::CheckActionChains`，统计最长输出链，长度 ≥ 3 时 `LogLevel::Info` 提示可以考虑合并节点（`:2968`–`:2974`）。
7. 若带 `TraceNodesComponent`，`env_->setNodeNameMap(underlyingPointerNameMap_)`（`:2975`–`:2977`）。

`finalizeForInterleaving()` 返回一个 `std::function<bool()>`，由调用方反复驱动，用于把图的推进与外部循环交织。

`detectCycle(bool includeFacility)`（`:2798`）是私有的；`includeFacility=false` 时先检查不含 facility 的环（真正的死循环），再用 `true` 检查含 facility 的环（可能是合法的反馈回路）。要故意组环的图必须在 Environment 里加 `graph_check_components::DontCheckCycles`：

```cpp
// 来源：tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:16-19（已简化）
using Env = infra::Environment<
    infra::CheckTimeComponent<true>
    , infra::graph_check_components::DontCheckCycles
    , ...
>;
```

`graph_check_components` 三个标记类见 `tm_infra/tm_kit/infra/GraphCheckComponents.hpp:7`-`:9`，详述在 [08-runners-and-control.md](08-runners-and-control.md)。

```cpp
template <class F> std::string getRegisteredName(std::shared_ptr<F> const &p);   // :2277
```

反查某个节点指针登记的名字，节点未注册时抛异常。

## 可视化

```cpp
void writeGraphVizDescription(std::ostream &os, std::string const &graphName);   // :2453
```

先 `doTouchups()` 再输出 digraph（实现 `:2461`）。节点名里的 `.` 变成 Graphviz 的 cluster 层级，`markStateSharing` 登记的共享关系也画出来。

**只生成图不运行**是极实用的调试手法——组完图、不调 `finalize()`、直接 return：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:146-151
if (generateGraphOnlyWithThisFile) {
    std::ofstream ofs(*generateGraphOnlyWithThisFile);
    r.writeGraphVizDescription(ofs, "simple_demo_main_logic");
    ofs.close();
    return;
}
```

`MainLogic.cpp` 的四个入口（`run_real_or_virtual`、`run_backtest`、`run_typecheck`）都有这段，命令行 `--generate_graph_only <file>` 触发。注意这样做会跳过 `finalize()` 的连通性校验，所以它能画出未连完的图——正好方便排查"为什么说某个输入没连"。

也可以边画边跑：

```cpp
// 来源：tm_examples/clock_logic_test/main.cpp:57-58
r.writeGraphVizDescription(std::cout, "test");
r.finalize();
```

## 最小可用示例：端到端

`tm_examples/simple_demo/plain_executables/MainLogic.cpp` 是全套文档的锚点，同一份业务组图 `MainLogicCombination` 被实时与回测两个入口复用。

实时版骨架（`run_real_or_virtual`，`:39`–`:180`，已大幅简化）：

```cpp
using M = infra::RealTimeApp<TheEnvironment>;   // :51
using R = infra::AppRunner<M>;                  // :52
TheEnvironment env;
R r(&env);                                      // :77

auto heartbeatSource = /* 广播监听 importer，返回 Source */;        // :79
auto inputDataSource = /* 通过心跳发现行情发布者 */;                 // :90
R::FacilitioidConnector<CalculateCommand,CalculateResult> calc = /* 远程或 mock */;  // :101

auto mainLogicOutput = MainLogicCombination(r, env, std::move(combinationInput), logicChoice, ...);  // :143
r.connect(std::move(inputDataSource), mainLogicOutput.dataSink);                                     // :144

r.finalize();                                   // :175
infra::terminationController(infra::TerminateAtTimePoint {
    infra::withtime_utils::parseLocalTodayActualTime(23, 59, 59)
});                                             // :177
```

回测版骨架（`run_backtest`，`:190`–`:259`，已大幅简化）：

```cpp
using M = infra::TopDownSinglePassIterationApp<TheEnvironment>;   // :197
using R = infra::AppRunner<M>;                                     // :198
TheEnvironment env;
R r(&env);                                                         // :203

auto importer = FileComponent::createImporter<...>(ifs, ...);      // :207
r.registerImporter("importer", importer);                          // :220
auto dataInput = r.execute(removeTopic, r.execute(parser, r.importItem(importer)));  // :224

auto mainLogicOutput = MainLogicCombination(r, env, std::move(combinationInput), logicChoice);  // :246
r.connect(dataInput.clone(), mainLogicOutput.dataSink);             // :247

r.finalize();                                                      // :256
infra::terminationController(infra::ImmediatelyTerminate {});      // :258
```

注意 `:247` 用的是 `dataInput.clone()`——因为 `dataInput` 在 `:230` 已经被 `setupExitTimer` 用过一次。

更声明式的组图写法见 [06-declarative-graph.md](06-declarative-graph.md)。

## 实时 / 回测行为差异

`AppRunner` 本身的 API 在两种模式下完全一致——这正是它的设计目标。差异来自 `App` 和 Environment：

| 维度 | RealTimeApp | TopDownSinglePassIterationApp |
|---|---|---|
| `finalize()` 之后 | 启动各节点线程，立即返回；靠 `terminationController` 挂住主线程 | 单线程拉动数据直到流结束 |
| 终止方式 | `TerminateAtTimePoint` / `RunForever` / `TerminateAfterDuration` | 一般 `ImmediatelyTerminate`（`finalize()` 返回时已跑完） |
| 组图期线程安全 | `AppRunner` 内部用 `recursive_mutex` 保护，可多线程组图 | 同样有锁，但通常单线程组图 |
| 环检测 | 同样执行 | 同样执行 |
| 连通度校验 | 同样执行 | 同样执行 |
| `markStateSharing` 的实际风险 | 高：共享状态被多线程并发访问，业务对象需自己加锁 | 低：单线程串行 |

`markStateSharing` 这一行差异值得单独强调：`MainLogicCombination.hpp:112` 声明的共享状态在实时模式下真的会被不同线程并发读写，业务类 `MainLogic` 必须自己保证线程安全；回测模式下则天然串行。

## 易错点

1. **一个 source 接多个 sink 必须 `clone()`。** `connect` 收 `Source<T>&&`，会把它消耗掉（`theSource() &&` 之后 `mSource` 被 move 走）。同一个 `Source` 对象第二次传给 `connect` 会在 `theSource()` 里抛 `std::runtime_error("Source is not initialized.")`（`WithTimeData.hpp:695`–`:698`）。正确做法是前 N-1 次用 `source.clone()`，最后一次用 `std::move(source)`：

   ```cpp
   // 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:94, :107
   heartbeatSource.clone()   // 第一次用
   heartbeatSource.clone()   // 第二次用
   ```

   这是组图代码里最高频的错误。`Source` 的拷贝构造也是 clone 语义（`:673`），所以按值传参同样安全；真正出事的是 `std::move` 用了两次。

2. **`preservePointer` 漏写导致悬垂。** 见上文。凡是节点用 `.get()` 捕获的 `shared_ptr`，组图函数返回前必须 `preservePointer`。

3. **facility 输出默认单连接。** 默认 `restrictFacilityOutputConnectionByDefault_ == true`，想复用一个 facility 必须 `setMaxOutputConnectivity` 或全局 `dontRestrictFacilityOutputConnectionByDefault()`。

4. **`actionAsSink_N_K` 的 N 要写对。** N 是 variant 的分支总数，不是"第几个"；K 才是下标。写错 N 的表现是模板不匹配，错误信息很长。

5. **`addTouchup` 在 touchup 阶段之后调用会抛异常。** 如果在 `writeGraphVizDescription` 之后又想接边，会撞上 `touchupDone_`——这也是"先画图再组图"行不通的原因。

6. **注册名唯一且 `.` 有特殊含义。** `.` 被当作层级分隔符，会影响 Graphviz 分簇与资源作用域解析。

7. **`finalize()` 只能调一次。** 重复调用会重复启动图。`writeGraphVizDescription` 可以在 `finalize()` 前后调，但 touchup 只会跑一遍。

8. **`Sink` 没有 `clone()`，但可以多次 `connect`。** 一个 sink 被多个 source 连是允许的（受 max input connectivity 限制，默认不限），这与 source 的单次消耗语义正好相反。

## 相关章节

- [00-overview.md](00-overview.md) —— 框架总览
- [01-app-types.md](01-app-types.md) —— `RealTimeApp` 与单遍迭代 App 的区别
- [02-environments.md](02-environments.md) —— Environment 与 component 混合
- [03-nodes-and-lifting.md](03-nodes-and-lifting.md) —— importer / exporter / action 与 lift
- [04-facilities.md](04-facilities.md) —— 四族 facility 与 `FacilitioidConnector`
- [06-declarative-graph.md](06-declarative-graph.md) —— `DeclarativeGraph` 声明式组图
- [07-time-and-data.md](07-time-and-data.md) —— 流动的数据包类型
- [08-runners-and-control.md](08-runners-and-control.md) —— `terminationController`、图校验组件、trace
- [09-generated-pieces.md](09-generated-pieces.md) —— `*_Piece.hpp` 生成文件体系
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
