---
title: 远程设施（on-order facility over transport）
library: tm_transport
headers: [tm_kit/transport/MultiTransportRemoteFacility.hpp, tm_kit/transport/MultiTransportRemoteFacilityManagingUtils.hpp, tm_kit/transport/MultiTransportFacilityWrapper.hpp, tm_kit/transport/SyntheticMultiTransportFacility.hpp, tm_kit/transport/RemoteTransactionSubscriberManagingUtils.hpp]
keywords: [MultiTransportRemoteFacility, MultiTransportRemoteFacilityManagingUtils, setupOneNonDistinguishedRemoteFacility, setupOneDistinguishedRemoteFacility, setupSimpleRemoteFacility, setupSimpleRemoteFacilitioid, setupSimpleRemoteFacilitioidByHeartbeat, setupTwoStepRemoteFacility, MultiTransportFacilityWrapper, facilityWrapper, facilityWrapperWithProtocol, SyntheticMultiTransportFacility, MultiTransportRemoteFacilityDispatchStrategy, ByteDataHookPair, SimpleRemoteFacilitySpecByHeartbeat, 远程设施, RPC, 请求响应, 服务注册]
---

# 远程设施（on-order facility over transport）

## 用途

广播是"一对多、无响应"，而 on-order facility（按单设施）是"一对一、有响应"：客户端发起请求（`Key<A>`），服务端处理并返回响应（`KeyedData<A,B>`），框架用 key 把响应配对回原来的请求。

在量化系统里，facility 用于：交易指令下达（下单请求 → 成交回报）、风控查询、配置变更、跨进程的服务调用。

`tm_transport` 提供三层封装：

1. **`MultiTransportRemoteFacility`** —— 底层节点，一个模板类，同时具备客户端与服务端行为，靠 wire 上的注册/注销消息在运行期确定角色。
2. **`MultiTransportRemoteFacilityManagingUtils<R>`** —— 用户主要打交道的接口：一行建立"带心跳服务发现"的客户端设施。
3. **`MultiTransportFacilityWrapper<R>`** —— 把**本地** facility（如纯内存实现的 mock）包成"从信道接收请求"的服务端，让同一个业务图既能在实时模式接网络，也能在测试模式接内存对象。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/MultiTransportRemoteFacility.hpp>
#include <tm_kit/transport/MultiTransportRemoteFacilityManagingUtils.hpp>
#include <tm_kit/transport/MultiTransportFacilityWrapper.hpp>
#include <tm_kit/transport/SyntheticMultiTransportFacility.hpp>
#include <tm_kit/transport/RemoteTransactionSubscriberManagingUtils.hpp>

namespace dev::cd606::tm::transport
```

## 核心类型与签名

### 1. 底层节点：`MultiTransportRemoteFacility`（`MultiTransportRemoteFacility.hpp:101`）

```cpp
template <class Env, class A, class B
    , class Identity = typename DetermineClientSideIdentityForRequest<Env,A>::IdentityType
    , MultiTransportRemoteFacilityDispatchStrategy DispatchStrategy
        = MultiTransportRemoteFacilityDispatchStrategy::Random
>
class MultiTransportRemoteFacility final
    : public /* ... AbstractOnOrderFacility / AbstractExporter / AbstractImporter 之一 ... */
{
    using M = infra::RealTimeApp<Env>;                    // :123
    using Input = std::conditional_t<...>;                // :125 有身份时是 tuple<Identity, Key<A>>
    using Output = B;                                     // :134
};
```

相关枚举（`MultiTransportRemoteFacility.hpp:33`、`:41`、`:91`）：

```cpp
enum class MultiTransportRemoteFacilityActionType { Register, Deregister };
enum class MultiTransportRemoteFacilityConnectionType {
    RabbitMQ, Redis, NATS, SocketRPC, GrpcInterop, JsonREST, WebSocket   // :42
};
enum class MultiTransportRemoteFacilityDispatchStrategy { Random, Designated };  // :92
```

`DispatchStrategy` 决定当同一个设施有多个服务端实例时如何选择：
- `Random` —— 随机派发（负载均衡），用于无状态服务
- `Designated` —— 按请求里携带的目标标识派发，用于有状态服务（如某个账号的下单必须送到持有该账号状态的进程）

wire 上的注册动作（`MultiTransportRemoteFacility.hpp:81`）：

```cpp
struct MultiTransportRemoteFacilityAction {
    MultiTransportRemoteFacilityActionType actionType;
    MultiTransportRemoteFacilityConnectionType connectionType;
    ConnectionLocator connectionLocator;
    std::string description;
};
using MultiTransportRemoteFacilityActionResult = std::tuple<MultiTransportRemoteFacilityAction, bool>;
```

**实务上不要直接实例化它**——用下面的 `ManagingUtils`。

### 2. 客户端：`MultiTransportRemoteFacilityManagingUtils<R>`（`MultiTransportRemoteFacilityManagingUtils.hpp:31`）

#### 2.1 无区分设施（推荐起点）

"无区分"（non-distinguished）指：同名的多个服务端实例被视为等价，客户端随机挑一个发请求。

```cpp
// :884
template <class Request, class Result>
static auto setupOneNonDistinguishedRemoteFacility(
    R &r
    , std::variant<
        typename R::template ConvertibleToSourceoid<HeartbeatMessage>
        , typename R::template ConvertibleToSourceoid<std::shared_ptr<HeartbeatMessage const>>
      > &&heartbeatSource
    , std::regex const &serverNameRE
    , std::string const &facilityRegistrationName
    , std::optional<ByteDataHookPair> hooks = std::nullopt
    , std::chrono::system_clock::duration ttl = std::chrono::seconds(3)
    , std::chrono::system_clock::duration checkPeriod = std::chrono::seconds(5)
) -> NonDistinguishedRemoteFacility<Request, Result>;

// :924 — 带协议包装的版本
template <template <class...> class ProtocolWrapper, class Request, class Result>
static auto setupOneNonDistinguishedRemoteFacilityWithProtocol(...);
```

返回的 `NonDistinguishedRemoteFacility<Request,Result>` 有成员 `.facility`（可直接赋给 `R::FacilitioidConnector<Request,Result>`）以及一个"底层可用实例计数"的 Source。

#### 2.2 有区分设施

```cpp
// :958 — 通过心跳发现，按 Designated 策略派发
template <class Request, class Result>
static auto setupOneDistinguishedRemoteFacility(...);

// :1001 / :1046 — 不走心跳，直接指定信道
template <class Request, class Result>
static auto setupOneDistinguishedRemoteFacility_NoHeartbeat(...);
```

#### 2.3 两步设施（先握手，再业务）

```cpp
// :1177
template <class FirstRequest, class FirstResult, class SecondRequest, class SecondResult>
static auto setupTwoStepRemoteFacility(
    R &r
    , std::variant<
        typename R::template ConvertibleToSourceoid<HeartbeatMessage>
        , typename R::template ConvertibleToSourceoid<std::shared_ptr<HeartbeatMessage const>>
      > &&heartbeatSource
    , std::regex const &serverNameRE
    , std::tuple<std::string, std::string> const &facilityRegistrationNames
    , std::function<FirstRequest()> firstRequestGenerator
    , std::function<bool(FirstRequest const &, FirstResult const &)> firstResultChecker
    , std::tuple<std::optional<ByteDataHookPair>, std::optional<ByteDataHookPair>> hooks
        = {std::nullopt, std::nullopt}
    , std::chrono::system_clock::duration ttl = std::chrono::seconds(3)
    , std::chrono::system_clock::duration checkPeriod = std::chrono::seconds(5)
) -> std::tuple<
    DistinguishedRemoteFacility<FirstRequest, FirstResult>
    , NonDistinguishedRemoteFacility<SecondRequest, SecondResult>
>;
```

典型用途是**先做密钥交换（Diffie-Hellman）再发业务请求**：`FirstRequest`/`FirstResult` 是握手消息，`SecondRequest`/`SecondResult` 是加密后的业务消息。`firstRequestGenerator` 在每次需要重新握手时生成新请求（如重新生成密钥对），`firstResultChecker` 验证握手结果（如处理对端公钥）。

#### 2.4 直接信道设施（不走心跳）

```cpp
// :1329 / :1494 / :1512 — 静态函数，不需要 R
template <class Request, class Result>
static auto setupSimpleRemoteFacility(
    std::string const &channelSpec
    , std::optional<ByteDataHookPair> hooks = std::nullopt
) -> typename R::template OnOrderFacilityPtr<Request, Result>;

// :1630 — 内部先建心跳订阅，再建设施；返回 facility + "首次就绪"触发源
template <class Request, class Result>
static auto setupSimpleRemoteFacilitioidByHeartbeat(
    R &r
    , std::string const &heartbeatSpec
    , std::string const &heartbeatTopic
    , std::regex const &facilityServerHeartbeatIdentityRE
    , std::string const &facilityRegistrationName
    , std::string const &prefix
    , std::optional<ByteDataHookPair> hooks = std::nullopt
    , std::optional<WireToUserHook> heartbeatHook = std::nullopt
    , std::chrono::system_clock::duration ttl = std::chrono::seconds(3)
    , std::chrono::system_clock::duration checkPeriod = std::chrono::seconds(5)
) -> SimpleRemoteFacilitioidForGraph<Request, Result>;

// :1680 — 统一入口，接受 variant<string, SimpleRemoteFacilitySpecByHeartbeat>
template <class Request, class Result>
static auto setupSimpleRemoteFacilitioid(
    R &r
    , SimpleRemoteFacilitySpec const &spec
    , std::string const &prefix
    , std::optional<ByteDataHookPair> hooks = std::nullopt
) -> SimpleRemoteFacilitioidForGraph<Request, Result>;
```

其中规格结构（`MultiTransportRemoteFacilityManagingUtils.hpp:16`）：

```cpp
struct SimpleRemoteFacilitySpecByHeartbeat {
    std::string heartbeatSpec;
    std::string heartbeatTopic;
    std::regex facilityServerHeartbeatIdentityRE;
    std::string facilityRegistrationName;
    std::optional<WireToUserHook> heartbeatHook = std::nullopt;
    std::chrono::system_clock::duration ttl = std::chrono::seconds(3);
    std::chrono::system_clock::duration checkPeriod = std::chrono::seconds(5);
};
using SimpleRemoteFacilitySpec = std::variant<std::string, SimpleRemoteFacilitySpecByHeartbeat>;
```

`ttl` 与 `checkPeriod`（默认 3 秒 / 5 秒）控制服务发现的时效：心跳超过 `ttl` 未更新则认为该服务端下线，每 `checkPeriod` 检查一次。

### 3. 服务端包装：`MultiTransportFacilityWrapper<R>`（`MultiTransportFacilityWrapper.hpp:17`）

把一个**本地已存在的** facility 暴露到信道上，供远端客户端调用。

```cpp
enum class MultiTransportFacilityWrapperOption {          // :12
    Default
    , NoReply
};

template <class R>
class MultiTransportFacilityWrapper {
public:
    // :23 — 给请求附加身份信息（有身份检查时必需）
    static auto addIdentity(...);

    // :1341 — 核心版本：返回一个"接受 R 与待包装 facility"的 lambda
    template <class A, class B
        , MultiTransportFacilityWrapperOption Option = MultiTransportFacilityWrapperOption::Default>
    static auto facilityWrapper(
        std::string const &channelSpec
        , std::string const &wrapperItemsNamePrefix
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    ) -> typename infra::AppRunner<M>::template FacilityWrapper<
            typename DetermineServerSideIdentityForRequest<Env,A>::FullRequestType, B>;

    // :1358 — 本地 facility 版本
    template <class A, class B>
    static auto localFacilityWrapper(...);

    // :1374 / :1390 — 带外部效果 / VIE facility 版本
    static auto facilityWithExternalEffectsWrapper(...);
    static auto vieFacilityWrapper(...);

    // :1406 — 指定协议包装
    template <template<class...> class ProtocolWrapper, class A, class B>
    static auto facilityWrapperWithProtocol(
        std::string const &channelSpec
        , std::string const &wrapperItemsNamePrefix
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    ) -> /* 同上，但 wire 走 ProtocolWrapper */;

    // :1423 / :1440 / :1457 — 对应的 local / external-effects / VIE 版本
    static auto localFacilityWrapperWithProtocol(...);
    static auto facilityWithExternalEffectsWrapperWithProtocol(...);
    static auto vieFacilityWrapperWithProtocol(...);
};
```

注意返回类型是 `FacilityWrapper<...>`——一个"接受 `R` 和 `std::shared_ptr<OnOrderFacility<...>>` 的 lambda"，而不是 `FacilitioidConnector`（`:1349`）。这正是示例里那种"把它塞进一个结构体字段、稍后再用"的用法能成立的原因。

如果不需要复用 wrapper 对象，用更直接的 `wrap` 静态函数（`:302`）：

```cpp
// :302 — 立即把已注册的 facility 暴露到信道；static void，直接操作 runner
template <class A, class B
    , MultiTransportFacilityWrapperOption Option = MultiTransportFacilityWrapperOption::Default>
static void wrap(
    R &runner
    , std::shared_ptr<typename M::template OnOrderFacility<
        typename DetermineServerSideIdentityForRequest<Env,A>::FullRequestType, B
      >> const &toBeWrapped
    , std::string const &channelSpec
    , std::string const &wrapperItemsNamePrefix
    , std::optional<ByteDataHookPair> hooks = std::nullopt
);

// :320 — 带协议包装
template <template<class...> class ProtocolWrapper, class A, class B, ...>
static void wrapWithProtocol(
    R &runner
    , std::shared_ptr<...> const &toBeWrapped
    , std::string const &channelSpec
    , std::string const &wrapperItemsNamePrefix
    , std::optional<ByteDataHookPair> hooks = std::nullopt
    , bool dontAddToHeartbeat = false
);
```

`wrap` 内部会调 `runner.getRegisteredName(toBeWrapped)` 取节点名用于心跳注册（`:293`）——**因此被包装的 facility 必须已经 `registerOnOrderFacility` 过**，否则心跳里没有名字、客户端发现不到它。`dontAddToHeartbeat=true` 可跳过这一步。

`facilityWrapper` 与 `localFacilityWrapper` 的区别：前者返回的 wrapper 会**建立真实网络监听**（服务端角色），后者只包装本地对象（用于同进程内的类型适配）。

### 4. 合成设施：`SyntheticMultiTransportFacility<R>`（`SyntheticMultiTransportFacility.hpp:17`）

**把 facility 跑在只支持广播的传输上**。

它的实现方式（`SyntheticMultiTransportFacility.hpp:66–77`、`:285–317`）：开**两个广播信道**——一个发请求，一个收回响应——然后用 `AppRunnerUtilComponents::syntheticRemoteFacility` 把这一对 `Sink`/`Source` 粘合成 `FacilitioidConnector<A,B>`。

这解释了"合成"的含义：facility 的请求-响应语义不是在传输层实现的（multicast/zeromq/nng 都不支持），而是**在应用层用两条广播信道合成出来的**。代价是没有真正的服务端寻址与派发——任何监听响应信道的人都能看到所有响应。

适用场景：需要在 multicast / ZeroMQ / NNG 这类无 facility 支持的传输上跑请求-响应；轻量集成测试。

```cpp
template <class R>
class SyntheticMultiTransportFacility {
public:
    using M = typename R::AppType;
    using Env = typename M::EnvironmentType;
    static_assert(infra::app_classification_v<M> == infra::AppClassification::RealTime,
        "SyntheticMultiTransportFacility can only be used for real time app");   // :22

    // :31 — 完整的请求-响应
    template <
        template<class... Xs> class OutgoingProtocolWrapper
        , template<class... Xs> class IncomingProtocolWrapper
        , class A, class B
        , bool MultiCallback
    >
    static auto client(
        R &r
        , std::string const &prefix
        , std::string const &outgoingSpec
        , std::string const &outgoingTopic
        , std::string const &incomingSpec
        , std::optional<std::string> const &incomingTopic
        , std::optional<ByteDataHookPair> hookPair = std::nullopt
    ) -> typename R::template FacilitioidConnector<A,B>;

    // :142 — 只发不收
    template <template<class...> class OutgoingProtocolWrapper, class A, bool AutoKeyify>
    static auto clientNoReply(
        R &r
        , std::string const &prefix
        , std::string const &outgoingSpec
        , std::string const &outgoingTopic
        , std::optional<UserToWireHook> outgoingHook = std::nullopt
    ) -> typename R::template Sink<std::conditional_t<AutoKeyify, A, typename M::template Key<A>>>;

    // :229 — 服务端：把一条本地 facility 接到"入站 spec / 出站 spec"两个信道
    template <
        template<class... Xs> class IncomingProtocolWrapper
        , template<class... Xs> class OutgoingProtocolWrapper
        , class A, class B
        , bool MultiCallback = false
    >
    static void server(
        R &r
        , std::string const &prefix
        , std::string const &incomingSpec
        , std::optional<std::string> const &incomingTopic
        , std::string const &outgoingSpec
        , std::string const &outgoingTopic
        , typename R::template FacilitioidConnector<
            typename DetermineServerSideIdentityForRequest<Env,A>::FullRequestType, B
          > const &facility
        , std::optional<ByteDataHookPair> hookPair = std::nullopt
    );
};
```

`client` + `server` 成对使用：`client` 的 `outgoingSpec` 对应 `server` 的 `incomingSpec`，`client` 的 `incomingSpec` 对应 `server` 的 `outgoingSpec`。

> **注意**：`SyntheticMultiTransportFacility` 要求 App 是 `RealTimeApp`（`static_assert` 在 `:22`）。它合成的是**传输层**，不是时钟层——所以它仍然用在实时 App 里，只是把 `spec` 指向本地内存总线而非网络。

### 5. 事务订阅客户端：`RemoteTransactionSubscriberManagingUtils`

`tm_kit/transport/RemoteTransactionSubscriberManagingUtils.hpp` 把 `tm_basic` 的 `transaction::v2` 订阅协议（见 [transaction v2](../tm_basic/09-transaction.md)）接到传输层：客户端通过 facility 发送订阅/退订请求，通过广播接收更新。

## 最小可用示例

### 客户端：带心跳服务发现的 facility

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:101–116`（已简化）

```cpp
R::FacilitioidConnector<CalculateCommand, CalculateResult> calc;
if (isReal) {
    calc = transport::MultiTransportRemoteFacilityManagingUtils<R>
        ::setupOneNonDistinguishedRemoteFacility<CalculateCommand, CalculateResult>(
            r
            , heartbeatSource.clone()
            , std::regex("simple_demo plain Calculator")   // 按心跳里的服务名匹配
            , "calculator facility"                        // 设施注册名
        ).facility;
} else {
    // 回测/离线模式：用本地 mock 替换，业务图完全不变
    calc = &(MockCalculatorCombination<
                R
                , basic::real_time_clock::ClockOnOrderFacility<TheEnvironment>
            >::service);
}
```

这个 `if/else` 是 TM Kit 处理"实时 vs 离线"的典型写法：`calc` 的类型始终是 `FacilitioidConnector<CalculateCommand,CalculateResult>`，两种模式下的下游代码一字不改。

### 服务端：把本地 facility 暴露到信道

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:118–142`（已简化）

```cpp
MainLogicInput<R> combinationInput {
    calc
    , {
        // 把配置变更 facility 同时暴露到 RabbitMQ 和 JSON REST 两个信道
        transport::MultiTransportFacilityWrapper<R>::facilityWrapperWithProtocol
            <basic::proto_interop::Proto, ConfigureCommandPOCO, ConfigureResultPOCO>(
            "rabbitmq://127.0.0.1::guest:guest:test_config_queue"
            , "cfg_wrapper_"
        )
        , transport::MultiTransportFacilityWrapper<R>::facilityWrapperWithProtocol
            <basic::nlohmann_json_interop::Json, ConfigureCommandPOCO, ConfigureResultPOCO>(
            "json_rest://0.0.0.0:34567:::/configureMainLogic"
            , "cfg_wrapper_2_"
        )
    }
    , transport::MultiTransportFacilityWrapper<R>::facilityWrapper
        <OutstandingCommandsQuery,OutstandingCommandsResult>(
        "rabbitmq://127.0.0.1::guest:guest:test_query_queue"
        , "query_wrapper_"
    )
    , transport::MultiTransportFacilityWrapper<R>::facilityWrapper
        <ClearCommands,ClearCommandsResult>(
        "rabbitmq://127.0.0.1::guest:guest:test_clear_queue"
        , "clear_cmd_wrapper_"
    )
};
```

注意：`facilityWrapper` 的第一个模板参数是请求/响应类型，函数参数是信道字符串与**节点名前缀**。

### 两步设施：先握手再业务

来源：`tm_examples/simple_demo/secure_executables/MainLogic.cpp:255–275`（已简化）

```cpp
calc = std::get<1>(
    transport::MultiTransportRemoteFacilityManagingUtils<R>
    ::template setupTwoStepRemoteFacility
        <DHHelperCommand, DHHelperReply, CalculateCommand, CalculateResult>
    (
        r
        , dhHeartbeatSource.clone()
        , std::regex("simple_demo secure Calculator")
        , { "dh_server_facility", "facility" }        // 两个设施的注册名
        , [&env, dhClientHelper]() -> DHHelperCommand {
            env.log(infra::LogLevel::Info, "Creating DH client command");
            return dhClientHelper->resetAndBuildCommand();   // 每次重新生成密钥
        }
        , [dhClientHelper](DHHelperCommand const &, DHHelperReply const &data) -> bool {
            dhClientHelper->process(data);                    // 处理对端公钥
            return true;
        }
    )
).facility;
```

返回 `tuple<DistinguishedRemoteFacility<FirstRequest,FirstResult>, NonDistinguishedRemoteFacility<SecondRequest,SecondResult>>`，业务设施是第二个元素。

## 实时 / 回测行为差异

远程设施是**纯实时概念**，但它与回测的对接方式很清晰：

| 维度 | 实时 | 回测 / 离线 |
|---|---|---|
| `setupOneNonDistinguishedRemoteFacility` | 建立真实网络连接 + 心跳服务发现 | **不可用**（底层节点硬编码 `RealTimeApp<Env>`，见 `MultiTransportRemoteFacility.hpp:123`） |
| 替代方案 | —— | 直接用一个本地 facility 对象（如 `MockCalculatorCombination::service`）赋给同一个 `FacilitioidConnector` 变量 |
| 服务发现 | 依赖心跳广播；`ttl`/`checkPeriod` 控制失效判定 | 无 |
| 派发策略 | `Random` 做负载均衡，`Designated` 按目标路由 | 单实例，无派发问题 |
| 时序 | 请求与响应异步，需处理超时与重试 | 同步调用，无网络延迟 |
| `MultiTransportFacilityWrapper` | 建立真实监听，接受远端调用 | 网络不可用时无法建立；回测通常不暴露服务端 |
| `SyntheticMultiTransportFacility` | 用内存总线替代网络，接口不变 | 同样可用（但要求 `RealTimeApp`）；用于"实时 App + 无网络"的集成测试 |

**示例中的真实用法**：`tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:292–301` 把同一个 transaction facility 用四种方式暴露——RabbitMQ、gRPC、WebSocket 各一路，第四路走**组播上的合成 facility**：

```cpp
// 来源：tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:292（已简化）
transport::SyntheticMultiTransportFacility<R>::server<
    basic::CBOR, basic::CBOR
    , TI::Transaction, TI::TransactionResponse
    , true                                     // MultiCallback：响应可多次
>(
    r
    , "transaction_wrapper_4/"
    , "multicast://224.0.0.1:34568:::db_one_list_transaction_input"   // 入站（请求）信道
    , "synthetic_transaction_input"
    , "multicast://224.0.0.1:34568:::db_one_list_transaction_output"  // 出站（响应）信道
    , "synthetic_transaction_output"
    , r.facilityConnector(transactionLogicCombinationRes.transactionFacility)
);
```

`MultiCallback=true` 表示一次请求可以产生多次响应（事务提交过程的中间回调），此时响应类型在 wire 上是 `Key<tuple<B,bool>>`，`bool` 是 `finalFlag`（`:259`）。

**推荐的架构模式**：把业务逻辑抽成模板，实时可执行文件注入网络设施，回测可执行文件注入本地 mock。`tm_examples/simple_demo/plain_executables/MainLogic.cpp:101–116` 就是这个模式的范本。

## 易错点

**1. `setupOneNonDistinguishedRemoteFacility` 返回的是结构体，要取 `.facility`**

返回类型 `NonDistinguishedRemoteFacility<Request,Result>` 不是 `FacilitioidConnector`。直接赋给 `FacilitioidConnector` 变量会编译失败，必须写 `.facility`（见示例 `MainLogic.cpp:110`）。同理 `setupTwoStepRemoteFacility` 返回 `tuple`，业务设施在 `std::get<1>`。

**2. 心跳源必须先建立，且服务端也要发出心跳**

`setupOneNonDistinguishedRemoteFacility` 的第一个参数就是 `heartbeatSource`。如果忘了先调 `oneBroadcastListener<HeartbeatMessage>`，或者服务端没有调 `attachHeartbeatAndAlertComponent` 注册自己，客户端会**永远等不到服务端**——表现为请求发出无响应，而不是报错。

**3. `ttl` 与 `checkPeriod` 的默认值（3 秒 / 5 秒）在跨机房场景偏紧**

`SimpleRemoteFacilitySpecByHeartbeat` 默认 `ttl = 3s`、`checkPeriod = 5s`。注意 `checkPeriod` **大于** `ttl`：意味着在两次检查之间，一个刚下线的服务端可能仍被派发请求。跨网络抖动较大的环境应同时放大两者，并保证 `checkPeriod < ttl` 或至少接近，以减少"派发给已死实例"的窗口。

**4. `DispatchStrategy::Random` 对无状态服务才对**

`MultiTransportRemoteFacility` 的默认派发策略是 `Random`（`MultiTransportRemoteFacility.hpp:101`）。如果服务端持有状态（如某个账号的持仓），多个实例间随机派发会导致状态不一致。有状态服务必须用 `Designated` 策略并把目标标识放进请求里。

**5. 有身份校验时请求类型会被包一层**

`MultiTransportRemoteFacility` 的 `Input` 类型是 `std::conditional_t<..., tuple<Identity, Key<A>>, Key<A>>`（`MultiTransportRemoteFacility.hpp:125`）。当环境配置了 identity checker 时，服务端收到的不是裸 `Key<A>`。用 `MultiTransportFacilityWrapper::addIdentity`（`:23`）处理这一层，不要手写。

**6. `facilityWrapperWithProtocol` 的协议包装要两端一致**

`facilityWrapperWithProtocol<Proto, A, B>` 声明 wire 上是 protobuf。客户端也必须用 `setupSimpleRemoteFacilityWithProtocol<Proto, A, B>` 或 `setupOneNonDistinguishedRemoteFacilityWithProtocol<Proto, A, B>`，否则一端发 protobuf 一端按 CBOR 解析，会得到解析错误或垃圾数据。

**7. `SyntheticMultiTransportFacility` 不能用于单程迭代 App**

`SyntheticMultiTransportFacility.hpp:22` 有 `static_assert(infra::app_classification_v<M> == infra::AppClassification::RealTime, ...)`。它是"用内存模拟网络"，而非"用内存模拟回测"——用在 `SinglePassIterationApp` 上会直接编译失败。

**8. `setupSimpleRemoteFacility` 的静态重载版本不需要 `R`**

`:1329` 的重载签名是 `setupSimpleRemoteFacility<Request,Result>(channelSpec, hooks)`，**没有 `R &r` 参数**；`:1512` 的重载有 `R &r`。两者都存在时，显式写模板参数可能产生歧义。推荐直接用带 `r` 的版本（`R` 可从参数推导）。

**9. 设施注册名必须与服务端一致**

客户端传的 `facilityRegistrationName` 必须与服务端 `attachHeartbeatAndAlertComponent` / 注册时用的名字完全一致（含大小写）。不一致时服务发现失败，同上——静默无响应。

## 第三方依赖

远程设施的依赖取决于所选传输（见 [01-broadcast.md](01-broadcast.md) 的依赖表）。facility 独有的是：

| 库 | 用途 | 头文件 | 官方文档 |
|---|---|---|---|
| Boost.Asio | `socket_rpc` 的 TCP 请求-响应 | `socket_rpc/SocketRPCOnOrderFacility.hpp` | https://www.boost.org/doc/libs/release/doc/html/boost_asio.html |
| gRPC | `grpc_interop` 的客户端/服务端设施 | `grpc_interop/GrpcClientFacility.hpp`、`GrpcServerFacility.hpp` | https://grpc.io/docs/languages/cpp/ |
| curlpp | `json_rest` 的 HTTP 客户端设施 | `json_rest/JsonRESTClientFacility.hpp` | http://www.curlpp.org/ |
| IXWebSocket | `websocket` 的客户端/服务端设施 | `websocket/WebSocketClientFacility.hpp`、`WebSocketServerFacility.hpp` | https://github.com/machinezone/IXWebSocket |

`MultiTransportRemoteFacility.hpp:1936` 起为该文件内的枚举与结构体提供了 CBOR 序列化特化（`RunCBORSerializer` / `RunCBORDeserializer`），因此注册/注销消息可以直接走任何传输。

## 相关章节

- [tm_transport 概览](00-overview.md) — 能力矩阵（哪些传输支持 facility）
- [广播](01-broadcast.md) — 心跳订阅是远程设施的前置条件
- [心跳与告警](05-heartbeat-and-alert.md) — `HeartbeatMessage`、`attachHeartbeatAndAlertComponent`
- [安全与身份校验](06-security.md) — `ByteDataHookPair`、`DetermineClientSideIdentityForRequest`
- [各传输详解](03-transports/) — `socket_rpc`、`grpc_interop`、`json_rest`、`websocket` 的 facility 用法
- [on-order facility 变体](../tm_infra/04-facilities.md) — `OnOrderFacility`、`FacilitioidConnector`、VIE facility
- [transaction v2](../tm_basic/09-transaction.md) — `RemoteTransactionSubscriberManagingUtils` 所封装的订阅协议
