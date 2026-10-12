---
title: AppRunnerUtils / MultiAppRunnerUtils / GraphControlFacility
library: tm_basic
headers: [tm_kit/basic/AppRunnerUtils.hpp, tm_kit/basic/MultiAppRunnerUtils.hpp, tm_kit/basic/GraphControlFacility.hpp]
keywords: [AppRunnerUtilComponents, MultiAppRunnerUtilComponents, graphControlFacility, GraphControlFacilityInput, wrapTuple2FacilitioidBySupplyingDefaultValue, convertIntoTuple2FacilitioidByDiscardingExtraValue, simulatedFacility, wrapFacilitioidConnector, wrapFacilitioidConnectorBackOnly, wrapFacilitioidConnectorFrontOnly, importWithTrigger, setupVIEFacilitySelfLoopAndWait, setupExitTimer, FacilitioidConnector, VIEFacility, 多图交错运行, 图控制, 退出计时器, 类型适配]
---

# AppRunnerUtils / MultiAppRunnerUtils / GraphControlFacility

## 用途

本章覆盖三个互补的 `AppRunner` 级工具：

- **`AppRunnerUtils.hpp`** — `AppRunnerUtilComponents<R>` 提供一系列对 `FacilitioidConnector` 进行类型适配、模拟与自环编排的静态方法，以及常用的 `setupExitTimer`（基于时钟的自动退出）工具。
- **`MultiAppRunnerUtils.hpp`** — `MultiAppRunnerUtilComponents::run` 将多个 `SinglePassIterationApp` runner 交错步进，实现同进程多图回测场景。
- **`GraphControlFacility.hpp`** — `graphControlFacility` 将 `AppRunner::controlAll` / `controlAllRE` 包装成一个 `OnOrderFacility`，允许外部请求（如网络命令）在运行期控制图内节点（暂停、恢复、改变参数等）。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/AppRunnerUtils.hpp>
#include <tm_kit/basic/MultiAppRunnerUtils.hpp>
#include <tm_kit/basic/GraphControlFacility.hpp>

namespace dev::cd606::tm::basic  // 所有类型均在此命名空间
```

`AppRunnerUtilComponents<R>` 以 `AppRunner` 类型 `R` 为模板参数（即 `infra::AppRunner<M>` 的实例化）；`MultiAppRunnerUtilComponents` 与 `graphControlFacility` 均不需要模板参数限制。

## 核心类型与签名

### 1. `AppRunnerUtilComponents<R>`（`AppRunnerUtils.hpp:16`）

所有方法均为 `static`，内部使用 `M = R::AppType`、`TheEnvironment = M::EnvironmentType`。

#### 1.1 `wrapTuple2FacilitioidBySupplyingDefaultValue`（`:22`）

将接受 `tuple<ToSupplyDefaultValue, Input>` 的 `FacilitioidConnector` 包装成只需要 `Input` 的版本，内部自动补充默认值。

```cpp
template <class Input, class Output, class ToSupplyDefaultValue>
static auto wrapTuple2FacilitioidBySupplyingDefaultValue(
    typename R::template FacilitioidConnector<
        std::tuple<ToSupplyDefaultValue, Input>, Output
    > toBeWrapped,
    std::string const &wrapPrefix,
    ToSupplyDefaultValue const &v = ToSupplyDefaultValue()
) -> typename R::template FacilitioidConnector<Input, Output>;
```

内部注册 `convert_key` 和 `convert_output` 两个 Action，以及一个 `discard_output` 导出器。使用了 `static bool insideConnected` 确保只注册一次。

#### 1.2 `convertIntoTuple2FacilitioidByDiscardingExtraValue`（`:87`）

与 1.1 方向相反：将接受 `Input` 的 `FacilitioidConnector` 包装成接受 `tuple<ExtraValue, Input>` 的版本，`ExtraValue` 被丢弃。内部用一个 `VIEOnOrderFacility` 实现请求转换。

```cpp
template <class Input, class Output, class ExtraValue>
static auto convertIntoTuple2FacilitioidByDiscardingExtraValue(
    typename R::template FacilitioidConnector<Input, Output> toBeConverted,
    std::string const &convertPrefix
) -> typename R::template FacilitioidConnector<
    std::tuple<ExtraValue, Input>, Output
>;
```

#### 1.3 `simulatedFacility`（`:158`，`:177`）

从一个 Sink（接收请求）和一个 Source（产生响应）构造 `FacilitioidConnector`，主要用于测试场景——可以替换真实 facility 而不改变调用侧代码。

```cpp
// Sink + Source 版本（输入需已注册）
template <class A, class B>
static auto simulatedFacility(
    typename R::template Sink<typename M::template Key<A>> const &inputHandler,
    typename R::template Source<typename M::template KeyedData<A,B>> &&outputProducer
) -> typename R::template FacilitioidConnector<A,B>;

// Sinkoid + Sourceoid 版本（可复制闭包）
template <class A, class B>
static auto simulatedFacility(
    typename R::template Sinkoid<typename M::template Key<A>> const &inputHandler,
    typename R::template Sourceoid<typename M::template KeyedData<A,B>> const &outputProducer
) -> typename R::template FacilitioidConnector<A,B>;
```

#### 1.4 `wrapFacilitioidConnector` 族（`:194`，`:262`，`:311`）

对 `FacilitioidConnector` 进行双向类型转换，使其接受/返回不同类型而无需修改内层 facility 代码。

```cpp
// 全双向：请求类型 A0↔A1，响应类型 B0↔B1
template <class A0, class B0, class A1, class B1>
static auto wrapFacilitioidConnector(
    KleisliFunction<A0,A1> const &forwardKeyTranslator,   // 请求方向
    KleisliFunction<A1,A0> const &backwardKeyTranslator,  // 响应 key 还原
    KleisliFunction<B1,B0> const &backwardDataTranslator, // 响应数据转换
    typename R::template FacilitioidConnector<A1,B1> const &innerFacilitioid,
    std::string const &prefix
) -> typename R::template FacilitioidConnector<A0,B0>;

// 仅响应方向转换（请求类型不变）
template <class A0, class B0, class B1>
static auto wrapFacilitioidConnectorBackOnly(
    KleisliFunction<B1,B0> const &backwardDataTranslator,
    typename R::template FacilitioidConnector<A0,B1> const &innerFacilitioid,
    std::string const &prefix
) -> typename R::template FacilitioidConnector<A0,B0>;

// 仅请求方向转换（响应类型不变）
template <class A0, class B0, class A1>
static auto wrapFacilitioidConnectorFrontOnly(
    KleisliFunction<A0,A1> const &forwardKeyTranslator,
    KleisliFunction<A1,A0> const &backwardKeyTranslator,
    typename R::template FacilitioidConnector<A1,B0> const &innerFacilitioid,
    std::string const &prefix
) -> typename R::template FacilitioidConnector<A0,B0>;
```

所有版本内部均通过注册 kleisli Action 实现转换，注册名以 `prefix` 为前缀（`/forwardKeyTranslator`、`/backwardTranslator`）。

#### 1.5 `importWithTrigger`（`:372`）

触发一个 `OnOrderFacilityWithExternalEffects` 并返回其外部输出 Source，可选择性地处理响应。

```cpp
template <class FacilityWithExternalEffects>
static typename R::template Source<
    typename infra::withtime_utils::ImporterTypeInfo<M,FacilityWithExternalEffects>::DataType
> importWithTrigger(
    R &r,
    typename R::template Source<typename M::template Key<InputType>> &&trigger,
    std::shared_ptr<FacilityWithExternalEffects> const &triggerHandler,
    std::optional<typename R::template Sink<...>> const &triggerResponseProcessor = std::nullopt,
    std::string const &triggerHandlerName = ""
);
```

返回值是该 facility 的外部广播 Source（相当于 `r.facilityWithExternalEffectsAsSource(triggerHandler)`）。若 `triggerHandlerName` 非空，函数内部自动注册该 facility。

#### 1.6 `setupVIEFacilitySelfLoopAndWait`（`:438`）

为一个 `VIEOnOrderFacility` 建立自环：外部触发 → 注入 ExtraInput → VIE facility 通过 ExtraOutput 触发回调 → 再次发起 Input 请求 → 直到 `extraOutputClassifierF` 返回 `false` 为止，然后将控制权交还给触发者。返回 `SetupVIEFacilitySelfLoopAndWaitOutput` 结构体，含：

```cpp
template <class OutsideBypassingData, class VIEFacility, class InjectF, class ExtraOutputClassifierF, class SelfLoopCreatorF, class InitialCallbackFilterF>
static SetupVIEFacilitySelfLoopAndWaitOutput<OutsideBypassingData,VIEFacility>
setupVIEFacilitySelfLoopAndWait(
    R &r,
    typename R::template Source<OutsideBypassingData> &&triggeringSource,
    InjectF &&injectF,             // OutsideBypassingData -> ExtraInput
    ExtraOutputClassifierF const &extraOutputClassifierF, // ExtraOutput -> bool (需要自环?)
    SelfLoopCreatorF &&selfLoopCreatorF,                  // ExtraOutput -> Input
    std::shared_ptr<VIEFacility> const &facility,
    InitialCallbackFilterF &&initialCallbackFilterF,       // KeyedData<Input,Output> -> bool
    std::string const &prefix = "",
    std::string const &facilityName = ""
);

struct SetupVIEFacilitySelfLoopAndWaitOutput {
    Sinkoid<Key<InputType>>              callIntoFacility;
    Source<KeyedData<InputType,OutputType>> facilityOutput;
    Source<ExtraOutputType>              facilityExtraOutput;
    Source<OutsideBypassingData>         nextTriggeringSource; // 自环结束后，转发原始触发数据
};
```

> **注意**（源码注释，`:424`）：`injectF` 必须是 1:1 纯转换，且从 ExtraInput 到 ExtraOutput 必须恰好产生一次 InitialCallback 或一次 ExtraOutput；框架无法校验此约束，违反将导致图不再推进。

#### 1.7 `setupExitTimer`（`:625`）

当输入 Source 第一次收到数据时，启动一个时钟，在 `exitAfterThisDurationFromFirstInput` 后调用 `wrapUpFunc` 并调用 `env->exit()`。

```cpp
template <class T>
static void setupExitTimer(
    R &r,
    typename M::Duration const &exitAfterThisDurationFromFirstInput,
    typename R::template Source<T> &&inputSource,
    std::function<void(TheEnvironment *)> wrapUpFunc,
    std::string const &componentNamePrefix
);
```

内部使用 `AppClockHelper<M>::Facility` 实现，配合 `LiftParameters::FireOnceOnly(true)` 确保只触发一次计时。当 `T` 为 `std::variant` 时，使用 `GenericExecute` 统一处理所有 variant 分支。

#### 1.8 `setupBackgroundClockAndExiter`（`:675`）

与 `setupExitTimer` 目的相同（保障单遍迭代模式下的退出），但**机制不同**：它注册一个**从 `startTime` 到 `exitTime` 的周期时钟**，每次 tick 检查是否已超过 `exitTime`，超过则调用 `wrapUpFunc` 并 `env->exit()`。

```cpp
template <class R>
static void setupBackgroundClockAndExiter(
    R &r
    , typename M::TimePoint const &startTime
    , typename M::TimePoint const &exitTime
    , typename M::Duration const &frequency
    , std::function<void(TheEnvironment *)> const &wrapUpFunc
    , std::string const &prefix
);
```

注册两个节点：importer `prefix+"/backgroundClock"` 与 exporter `prefix+"/exiter"`（`:688`、`:696`）。

**`if constexpr` 守卫**（`:683`）：函数体只在 `M` 是 `SinglePassIterationApp` 或 `TopDownSinglePassIterationApp` 时才生成，其他 App 类型下调用它是**空操作**（不报错）。这与 `setupExitTimer` 形成互补：

| | `setupExitTimer` | `setupBackgroundClockAndExiter` |
|---|---|---|
| 触发条件 | 输入 Source 的**第一条数据** | **时间**到达 `exitTime` |
| 适用 App | 任何（实时/回测都行） | 仅单遍迭代（其他 App 下为空操作） |
| 典型用途 | 链读取完成后自动退出 | 回测的固定时长窗口 |

用法示例见 `tm_examples/simple_demo_chain_version/executables/single_pass/main.cpp`。

#### 1.9 Pathway 辅助（`:711`、`:723`）

把"连接方式"本身抽成可复用的值：

```cpp
// :711 — 把单个 Action 包装成 Pathway
template <class A, class B>
static typename R::template Pathway<A,B> singleActionPathway(
    typename R::template ActionPtr<A,B> const &action
);

// :723 — 把 facility 包装成 Pathway
template <class A, class B>
static typename R::template Pathway<A,B> singleFacilityPathway(
    typename R::template FacilitioidConnector<A,B> facility
    , std::string const &prefix
);
```

`Pathway<A,B>`（定义在 `tm_infra/tm_kit/infra/WithTimeData.hpp:3295`）是"接受 `(R&, Source<A>&&, Sink<B>)` 并完成连接"的闭包——用于把一段子图封装成可传递、可组合的单元。

---

### 2. `MultiAppRunnerUtilComponents`（`MultiAppRunnerUtils.hpp:9`）

不以 `AppRunner` 或 `M` 为模板参数的非模板类，只有一个公开方法：

```cpp
class MultiAppRunnerUtilComponents {
public:
    template <class... Rs>
    static void run(Rs &... rs);  // :34
};
```

`run` 内部调用每个 runner 的 `finalizeForInterleaving()`，获得一个 `function<bool()>` 步进器，然后在一个 `while(true)` 循环中轮询所有步进器，直到全部返回 `false`（无更多事件）为止。

**适用场景**：同一进程中运行两个或更多使用不同 `SinglePassIterationApp` runner 的子图（例如两个环境组合不同的业务图），通过 `triggerImporterWithTime`"虫洞"跨 runner 传递数据。

---

### 3. `GraphControlFacilityInput` 与 `graphControlFacility`（`GraphControlFacility.hpp`）

```cpp
// :8 — 字段宏
#define TM_KIT_BASIC_GRAPH_CONTROL_FACILITY_INPUT_FIELDS \
    ((std::optional<std::string>, name)) \
    ((std::optional<std::string>, nameRE)) \
    ((std::string, command)) \
    ((std::vector<std::string>, params))

// :14 — 带 CBOR 序列化的请求结构体
TM_BASIC_CBOR_CAPABLE_STRUCT(GraphControlFacilityInput, ...);

// :17 — 工厂函数，Output 默认为 VoidStruct
template <class R, class Output = VoidStruct>
inline auto graphControlFacility(R &r, std::string const &facilityName);
// 返回 shared_ptr<OnOrderFacility<GraphControlFacilityInput, Output>>
```

`graphControlFacility` 创建一个 `liftPureOnOrderFacility`，其处理函数：
- 若 `name` 非空 → `r.controlAll(name, command, params)`
- 若 `nameRE` 非空 → `r.controlAllRE(regex(nameRE), command, params)`
- 返回 `Output {}`（默认构造）

`command` 和 `params` 语义由 `AppRunner::controlAll` 定义（见 `tm_infra/05-app-runner.md`），通常用于控制 `ControllableNode`（如暂停、设置参数等）。

`GraphControlFacilityInput` 已注册 CBOR 序列化（文件末尾的 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE`），可通过网络传输。

## 最小可用示例

### setupExitTimer：SinglePassIterationApp 安全退出

来源：`tm_examples/simple_demo_chain_version/executables/print_chain/main.cpp:51–59`

```cpp
#include <tm_kit/basic/AppRunnerUtils.hpp>
using R = infra::AppRunner<M>;

template <class Env>
void run(Env *env, std::string const &chainLocatorStr) {
    R r(env);

    auto chainDataSource = basic::simple_shared_chain::createChainDataSource<R, ChainData>(
        r, /* ...readerFactory... */, "input_chain"
    );

    // 第一条数据到达后，24 小时内自动退出
    basic::AppRunnerUtilComponents<R>::setupExitTimer(
        r,
        std::chrono::hours(24),
        chainDataSource.clone(),
        [](Env *env) {
            env->log(infra::LogLevel::Info, "Wrapping up!");
        },
        "exitTimerPart"
    );

    auto printer = M::template pureExporter<ChainData>([env](ChainData &&d) {
        env->log(infra::LogLevel::Info, /*...*/);
    });
    r.exportItem("printer", printer, chainDataSource.clone());
    r.finalize();
}
```

`setupExitTimer` 在 `SinglePassIterationApp` 中尤其有用：`finalFlag` 可能被某个返回 `nullopt` 的 Action 丢失，显式计时器是可靠的退出保障。

### MultiAppRunnerUtilComponents::run：双图交错回测

来源：`tm_examples/common_flow_util_tests/TwoRunnerTest.cpp:90–107`

```cpp
#include <tm_kit/basic/MultiAppRunnerUtils.hpp>

void runSinglePass() {
    using M1 = infra::SinglePassIterationApp<Env1>;
    using M2 = infra::SinglePassIterationApp<Env2>;
    infra::AppRunner<M1> r1(&env1);
    infra::AppRunner<M2> r2(&env2);

    // 虫洞：M2 的 triggerImporter 接受 M1 产生的数据
    auto wormhole = M2::template triggerImporterWithTime<std::string>();
    r2.registerImporter("wormholeIn", std::get<0>(wormhole));

    auto now = env1.now();
    graph1(now, r1, std::get<1>(wormhole));     // graph1 向虫洞发数据
    graph2(now, r2, r2.importItem(std::get<0>(wormhole)));

    // 交错步进两个 runner，直到事件队列全空
    basic::MultiAppRunnerUtilComponents::run(r1, r2);
}
```

### wrapFacilitioidConnectorBackOnly：响应类型适配

```cpp
// 来源：典型 facility 类型适配模式（已简化）
#include <tm_kit/basic/AppRunnerUtils.hpp>
using ARU = basic::AppRunnerUtilComponents<R>;

// 内部 facility 返回 InternalResult，但外部调用方期望 ExternalResult
auto innerFacilitioid = /* ... FacilitioidConnector<Request, InternalResult> ... */;

auto backwardConvert = infra::KleisliUtils<M>::template liftPure<InternalResult>(
    [](InternalResult &&r) -> ExternalResult {
        return ExternalResult { r.code, r.message };
    }
);

auto outerFacilitioid = ARU::template wrapFacilitioidConnectorBackOnly<
    Request, ExternalResult, InternalResult
>(backwardConvert, innerFacilitioid, "myFacility");
```

## 实时 / 回测行为差异

| 功能 | 实时 (`RealTimeApp`) | 回测 (`SinglePass`/`TopDown`) |
|---|---|---|
| `setupExitTimer` | 使用 `AppClockHelper<M>::Facility` 的实时时钟计时 | 使用回测时钟事件驱动计时；实际"墙钟"时间不计，以虚拟时间为准 |
| `MultiAppRunnerUtilComponents::run` | **不适用**：`RealTimeApp` 没有 `finalizeForInterleaving()` 方法 | 交错步进多个 SinglePass runner；适用于多图回测 |
| `wrapTuple2Facilitioid` / `wrapFacilitioidConnector` 族 | 两种模式行为完全一致（纯数据流变换，无时间依赖） | 同左 |
| `importWithTrigger` | 返回实时广播 Source，facility 后台线程产生推送 | 返回事件队列 Source，由 facility 的 `generate()` 驱动 |
| `setupVIEFacilitySelfLoopAndWait` | 需要自环对应的 1:1 约束；多线程下需保证 facility 线程安全 | SinglePass 单线程无竞争，但 1:1 约束同样必须满足 |

## 易错点

**1. `wrapTuple2FacilitioidBySupplyingDefaultValue` 使用 `static bool` 标记，多次调用只有第一次注册节点**  
函数内部用 `static bool insideConnected` 防止重复注册（`:65`）。这意味着同一份 `toBeWrapped` 对象若被调用两次，第二次调用时不会再次注册内部节点，但仍会调用 `r.execute(convertKeyCopy, std::move(source))`——即发送方连接仍然有效，只是内部节点已经存在。如果需要将同一个 toBeWrapped 连接到多个上游，应复用同一个包装结果而非多次调用。

**2. `convertIntoTuple2FacilitioidByDiscardingExtraValue` 内部创建 VIE facility，需要 `AbstractIntegratedVIEOnOrderFacilityWithPublish` 支持**  
该函数（`:87`）内部定义了一个 `LocalF` 类继承 `AbstractIntegratedVIEOnOrderFacilityWithPublish`，并调用 `M::template vieOnOrderFacility` 创建节点。这意味着 App 类型 `M` 必须支持 VIE facility——`RealTimeApp` 和 `SinglePassIterationApp`/`TopDownSinglePassIterationApp` 均支持，但自定义 App 类型可能不行。

**3. `MultiAppRunnerUtilComponents::run` 仅适用于 `SinglePassIterationApp`**  
`run` 依赖每个 runner 提供 `finalizeForInterleaving()`，这个方法只存在于 `SinglePassIterationApp` 的 runner 上。对 `RealTimeApp` 的 runner 调用 `run` 会编译失败（无 `finalizeForInterleaving` 成员）。正确的多图实时模式是直接分别调用每个 runner 的 `start()`。

**4. `setupVIEFacilitySelfLoopAndWait` 的 1:1 约束必须由用户保证**  
源码注释（`:424–437`）明确指出：`injectF` 必须是纯 1:1 转换，且每次通过 ExtraInput 调用 VIE facility 必须恰好产生一次"初始回调"或一次 ExtraOutput。框架内部没有超时或错误检测机制——若 facility 失败、挂起或产生多于一次输出，`synchronizer2` 将永久等待而图不再推进。在实时模式下这会导致程序卡死；在回测模式下则会让事件队列耗尽后直接退出。

**5. `graphControlFacility` 的 `command`/`params` 语义由 `ControllableNode` 实现决定**  
`graphControlFacility` 本身不定义 `command` 的含义；它只是将请求转发给 `r.controlAll`/`r.controlAllRE`。实际行为取决于图中哪些节点实现了 `ControllableNode` 接口以及它们如何响应命令字符串。若发送了未知命令，节点会静默忽略（`AppRunner` 不报错）。

**6. `setupExitTimer` 在 `SinglePassIterationApp` 中依赖 `finalFlag` 正常传播到计时触发路径上**  
`setupExitTimer` 用 `FireOnceOnly(true)` 保证只设置一次计时器，触发条件是 `inputSource` 上第一个事件。若该 Source 从未产生任何事件（例如链为空），计时器永远不会启动，`SinglePassIterationApp` 仍可能通过 `finalFlag` 正常退出。但如果图既无事件也无 `finalFlag`，程序不会退出。应确保至少有一条退出路径有效。

**7. `wrapFacilitioidConnector` 中 `backwardKeyTranslator` 可能返回 `nullopt`，导致响应被静默丢弃**  
当 `backwardKeyTranslator` 的 kleisli 返回 `nullopt` 时（`:228`），整条响应被过滤掉，调用方的 `KeyedData` sink 永远收不到该响应。这相当于请求超时（无响应），但不会报错。在设计 key 还原逻辑时需确保反向转换对所有合法输出都能成功。

## 第三方依赖

- **Boost.UUID** — `AppRunnerUtils.hpp` 间接引入（通过 `AppClockHelper.hpp`），`setupExitTimer` 内部的 `keyify` 使用 UUID 生成请求 ID。vcpkg 包名：`boost-uuid`。
- 无其他直接第三方依赖；所有功能均基于 `tm_infra` 核心接口与标准库。

## 相关章节

- [AppRunner 连接与控制](../tm_infra/05-app-runner.md) — `controlAll`、`controlAllRE`、`ControllableNode`、`finalizeForInterleaving`
- [CommonFlowUtils 节点组合工具](05-common-flow-util.md) — 与 `AppRunnerUtils` 互补；`synchronizer2`（`setupVIEFacilitySelfLoopAndWait` 内部使用）
- [on-order facility 变体](../tm_infra/04-facilities.md) — `OnOrderFacilityWithExternalEffects`（`importWithTrigger` 目标类型）、`VIEOnOrderFacility`（`setupVIEFacilitySelfLoopAndWait` 目标类型）
- [时钟与 AppClockHelper](01-clocks.md) — `setupExitTimer` 内部使用 `AppClockHelper<M>::Facility`
- [transaction v2 服务端组合](09-transaction.md) — `transactionLogicCombination` 返回的 `FacilitioidConnector` 可通过 `wrapFacilitioidConnector` 族做类型适配后暴露给外部
