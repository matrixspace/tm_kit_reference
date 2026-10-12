---
title: 广播：listener 与 publisher
library: tm_transport
headers: [tm_kit/transport/MultiTransportBroadcastListener.hpp, tm_kit/transport/MultiTransportBroadcastListenerManagingUtils.hpp, tm_kit/transport/MultiTransportBroadcastPublisherManagingUtils.hpp, tm_kit/transport/MultiTransportBroadcastListenerManagingUtils_SynchronousRunner.hpp]
keywords: [MultiTransportBroadcastListener, MultiTransportBroadcastPublisherManagingUtils, MultiTransportBroadcastListenerManagingUtils, oneBroadcastListener, oneBroadcastPublisher, setupBroadcastListeners, setupBroadcastListenersWithTopic, oneBroadcastListenerWithTopic, oneBroadcastListenerWithProtocol, oneBroadcastPublisherWithProtocol, oneByteDataBroadcastListener, oneByteDataBroadcastPublisher, setupBroadcastListenerThroughHeartbeat, MultiTransportBroadcastFirstUpdateQueryManagingUtils, fetchFirstUpdateAndDisconnect, MultiTransportBroadcastListenerSpec, topicDescription, 广播, 订阅, 发布, 服务发现]
---

# 广播：listener 与 publisher

## 用途

广播是"一对多、无响应"的通信模式。一个 publisher 往某个信道写数据，任意多个 listener 订阅该信道；publisher 不知道也不关心谁在听。

在量化系统里，广播用于：行情分发（一个行情源 → 多个策略进程）、心跳与状态通告（服务发现的基础）、配置下发、风控信号推送。

`tm_transport` 把这套模式封装成两个 `ManagingUtils` 类，业务代码只需给出**信道字符串**和**数据类型**，不必知道底层是 RabbitMQ 还是 ZeroMQ。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/MultiTransportBroadcastListener.hpp>
#include <tm_kit/transport/MultiTransportBroadcastListenerManagingUtils.hpp>
#include <tm_kit/transport/MultiTransportBroadcastPublisherManagingUtils.hpp>

namespace dev::cd606::tm::transport
```

## 核心类型与签名

### 1. 底层节点：`MultiTransportBroadcastListener`（`MultiTransportBroadcastListener.hpp:339`）

这是真正干活的节点，继承自 `RealTimeApp<Env>::AbstractIntegratedOnOrderFacilityWithExternalEffects<MultiTransportBroadcastListenerInput, MultiTransportBroadcastListenerOutput, basic::TypedDataWithTopic<T>>` 和 `IControllableNode<Env>`。

它的输入是**订阅管理指令**，外部输出是**订阅到的数据**：

```cpp
// :233 — 输入类型
using MultiTransportBroadcastListenerInput = basic::CBOR<
    std::variant<
        MultiTransportBroadcastListenerAddSubscription
        , MultiTransportBroadcastListenerRemoveSubscription
        , MultiTransportBroadcastListenerRemoveAllSubscriptions
    >
>;
// :240 — 输出类型
using MultiTransportBroadcastListenerOutput = basic::CBOR<
    std::variant<
        MultiTransportBroadcastListenerAddSubscriptionResponse
        , MultiTransportBroadcastListenerRemoveSubscriptionResponse
        , MultiTransportBroadcastListenerRemoveAllSubscriptionsResponse
    >
>;
```

订阅描述结构体（`MultiTransportBroadcastListener.hpp:157`）：

```cpp
struct MultiTransportBroadcastListenerAddSubscription {
    MultiTransportBroadcastListenerConnectionType connectionType;  // :159
    ConnectionLocator connectionLocator;                            // :160
    std::string topicDescription;                                   // :161
};
struct MultiTransportBroadcastListenerRemoveSubscription {
    MultiTransportBroadcastListenerConnectionType connectionType;  // :194
    uint32_t subscriptionID;
};
struct MultiTransportBroadcastListenerRemoveAllSubscriptions {};    // :205
```

构造函数与 `IControllableNode` 接口（`MultiTransportBroadcastListener.hpp:1047`）：

```cpp
MultiTransportBroadcastListener(std::optional<WireToUserHook> wireToUserHook = std::nullopt);
void start(Env *env) override final;      // :1059，空实现
void handle(InnerData<Key<MultiTransportBroadcastListenerInput>> &&input) override final;  // :1061
void control(Env *env, std::string const &command, std::vector<std::string> const &params) override final;  // :1064
```

`control` 支持两个命令（`MultiTransportBroadcastListener.hpp:1064`）：
- `"stop"` —— 发一条 `RemoveAllSubscriptions`，取消全部订阅并把当前订阅记入 `restartInfo_`
- `"restart"` —— 从 `restartInfo_` 恢复全部订阅

订阅记录用 `std::map<SubscriptionRecKey, MultiTransportBroadcastListenerAddSubscription>` 保存，其中 `SubscriptionRecKey = std::tuple<ConnectionType, uint32_t>`（`MultiTransportBroadcastListener.hpp:363`）。

**实务上你几乎不会直接实例化它**——用下面两个 `ManagingUtils` 类。

### 2. 发布端：`MultiTransportBroadcastPublisherManagingUtils<R>`（`MultiTransportBroadcastPublisherManagingUtils.hpp:22`）

```cpp
template <class R>
class MultiTransportBroadcastPublisherManagingUtils {
public:
    using M = typename R::AppType;
    using Env = typename R::EnvironmentType;

    // :28 — 主入口。返回 Sink<TypedDataWithTopic<OutputType>>
    template <class OutputType>
    static auto oneBroadcastPublisher(
        R &r
        , std::string const &name
        , std::string const &channelSpec
        , std::optional<UserToWireHook> hook = std::nullopt
        , bool threaded = false
    ) -> typename R::template Sink<basic::TypedDataWithTopic<OutputType>>;

    // :174 — 已序列化的字节流版本
    static auto oneByteDataBroadcastPublisher(
        R &r
        , std::string const &name
        , std::string const &channelSpec
        , std::optional<UserToWireHook> hook = std::nullopt
        , bool threaded = false
    ) -> typename R::template Sink<basic::ByteDataWithTopic>;

    // :302 — 指定 wire 协议包装（Proto / Json / CBOR / std::void_t）
    template <template<class... Xs> class ProtocolWrapper, class OutputType>
    static auto oneBroadcastPublisherWithProtocol(
        R &r
        , std::string const &name
        , std::string const &channelSpec
        , std::optional<UserToWireHook> hook = std::nullopt
        , bool threaded = false
    ) -> typename R::template Sink<basic::TypedDataWithTopic<OutputType>>;
};
```

注意返回类型是 `Sink<TypedDataWithTopic<T>>` 而不是 `Sink<T>`——广播数据总是带 topic，需要在上游用 `basic::SerializationActions<M>::addConstTopic<T>("...")` 之类补上 topic。

`threaded=true` 时，函数内部会插入一个 `SuggestThreaded(true)` 的 kleisli 包装节点（名称为 `name+":threadWrapper"`），把序列化与发送挪到后台线程，避免阻塞主数据流。

`oneBroadcastPublisher` 对不可直接序列化的 `OutputType` 会自动套一层 `basic::CBOR<T>`（`MultiTransportBroadcastPublisherManagingUtils.hpp:36`）。

### 3. 订阅端：`MultiTransportBroadcastListenerManagingUtils<R>`（`MultiTransportBroadcastListenerManagingUtils.hpp:31`）

一个函数族，按"数量 × 是否带 topic × 协议包装"组合：

```cpp
template <class R>
class MultiTransportBroadcastListenerManagingUtils {
public:
    using M = typename R::AppType;
    using Env = typename R::EnvironmentType;

    // 类型别名
    template <class ... InputTypes>
    using BroadcastListeners = std::tuple<typename R::template Sourceoid<InputTypes>...>;   // :44
    template <class ... InputTypes>
    using BroadcastListenersWithTopic =
        std::tuple<typename R::template Sourceoid<basic::TypedDataWithTopic<InputTypes>>...>;  // :49

    // ---- 多路批量 ----
    // :296 — 一次建立多个订阅，返回 Sourceoid 元组；容忍不支持的传输
    template <class ... InputTypes>
    static auto setupBroadcastListeners(
        R &r
        , std::tuple<MultiTransportBroadcastListenerSpec<InputTypes>...> const &specs
        , std::string const &prefix
        , std::function<std::optional<WireToUserHook>(std::string const &)> const &hookFactory
            = [](std::string const &) {return std::nullopt;}
    ) -> BroadcastListeners<InputTypes...>;

    // :314 — 同上，但每路输出保留 topic
    template <class ... InputTypes>
    static auto setupBroadcastListenersWithTopic(...) -> BroadcastListenersWithTopic<InputTypes...>;

    // ---- 单路 ----
    // :337 — 最常用。返回 Source<InputType>，不含 topic
    template <class InputType>
    static auto oneBroadcastListener(
        R &r
        , std::string const &namePrefix
        , std::string const &channelSpec
        , std::optional<std::string> const &topicDescription = std::nullopt
        , std::optional<WireToUserHook> hook = std::nullopt
    ) -> typename R::template Source<InputType>;

    // :365 — 指定协议包装
    template <template<class...> class ProtocolWrapper, class InputType>
    static auto oneBroadcastListenerWithProtocol(...) -> typename R::template Source<InputType>;

    // :406 — 保留 topic
    template <class InputType>
    static auto oneBroadcastListenerWithTopic(...) -> typename R::template Source<basic::TypedDataWithTopic<InputType>>;

    // :434 — 保留 topic + 协议包装
    template <template<class...> class ProtocolWrapper, class InputType>
    static auto oneBroadcastListenerWithTopicWithProtocol(...) -> typename R::template Source<basic::TypedDataWithTopic<InputType>>;

    // :485 — 字节流版本
    static auto oneByteDataBroadcastListener(
        R &r
        , std::string const &name
        , std::string const &channelSpec
        , std::optional<std::string> const &topicDescription = std::nullopt
        , std::optional<WireToUserHook> hook = std::nullopt
    ) -> typename R::template Source<basic::ByteDataWithTopic>;

    // ---- 基于心跳的服务发现 ----
    // :683 — 通过心跳发现远端，再订阅其广播
    template <class InputType>
    static auto setupBroadcastListenerWithTopicThroughHeartbeat(
        R &r
        , std::variant<
            typename R::template ConvertibleToSourceoid<HeartbeatMessage>
            , typename R::template ConvertibleToSourceoid<std::shared_ptr<HeartbeatMessage const>>
          > &&heartbeatSource
        , std::regex const &serverNameRE
        , std::string const &broadcastSourceLookupName
        , std::string const &broadcastTopic
        , std::string const &prefix
        , std::optional<WireToUserHook> const &hook = std::nullopt
        , std::function<bool(basic::TypedDataWithTopic<InputType> const &)> stopCriteria = {}
    ) -> typename R::template Source<basic::TypedDataWithTopic<InputType>>;

    // :755 — 同上，去掉 topic
    template <class InputType>
    static auto setupBroadcastListenerThroughHeartbeat(...) -> typename R::template Source<InputType>;
};
```

#### `MultiTransportBroadcastListenerSpec`（`MultiTransportBroadcastListenerManagingUtils.hpp:24`）

```cpp
template <class InputType>
struct MultiTransportBroadcastListenerSpec {
    std::string name;                          // 节点名前缀
    std::string channel;                       // 信道字符串
    std::optional<std::string> topicDescription;   // 可选 topic
}; //InputType 放在签名里是为了强制类型安全
```

#### 两种函数的**错误策略不同**

这是选用时的关键区别：

- `oneBroadcastListener` / `oneBroadcastListenerWithTopic` —— 无法建立监听时**抛 `std::runtime_error`**（`:360`、`:429`）。源码注释（`:332`）解释了理由：这两个函数预期传入"准常量"的信道字符串（不来自网络），所以宁可快速失败。
- `setupBroadcastListeners` / `setupBroadcastListenersWithTopic` —— **容忍不支持的传输**。源码注释（`:290`）说明：这类函数可能被用来"监听外部消息并据此建立订阅"，如果远端发布了本程序不支持的传输，不应该导致程序崩溃。

### 4. `MultiTransportBroadcastFirstUpdateQueryManagingUtils<Env>`（`MultiTransportBroadcastListenerManagingUtils.hpp:784`）

同步查询工具：连接信道、取第一条（满足谓词的）数据、然后断开。返回 `std::future`。

```cpp
template <class Env>
class MultiTransportBroadcastFirstUpdateQueryManagingUtils {
public:
    // :794
    static std::future<basic::ByteDataWithTopic> fetchFirstUpdateAndDisconnect(
        Env *env
        , std::string const &channelSpec
        , std::optional<std::string> const &topicDescription = std::nullopt
        , std::optional<WireToUserHook> hook = std::nullopt
    );

    // :921
    template <class T>
    static std::future<basic::TypedDataWithTopic<T>> fetchTypedFirstUpdateAndDisconnect(
        Env *env
        , std::string const &channelSpec
        , std::optional<std::string> const &topicDescription = std::nullopt
        , std::function<bool(T const &)> predicate = std::function<bool(T const &)>()
        , std::optional<WireToUserHook> hook = std::nullopt
    );
};
```

用途：进程启动时读一次初始快照（如最新配置、当前持仓），不需要长期订阅。

### 5. topic 的通配符适配

不同传输的通配符语法不同，框架做了自动转换（`MultiTransportBroadcastListener.hpp:248`、`:256`、`:265`）：

| 传输 | topic 为空时的默认值 | `#` 的处理 |
|---|---|---|
| RabbitMQ | `"#"`（匹配所有） | 原样保留（AMQP 的 `#` 就是多级通配） |
| Redis | `"*"` | **替换为 `*`**（Redis glob 用 `*`） |
| NATS | `">"`（匹配所有） | **替换为 `*`**（NATS 用 `>` 作多级通配，`*` 作单级） |
| 其他 | `Component::NoTopicSelection{}` | 若写成 `r/.../` 形式则解析为正则 |

所以写 `"simple_demo.plain_executables.#.heartbeat"` 一份 topic，在 RabbitMQ、Redis、NATS 上都能工作。

## 最小可用示例

### 发布端：同一份数据发往多个信道

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:70–96`（已简化）

```cpp
using R = infra::AppRunner<M>;
R r(&env);

// 先给数据加上固定 topic
auto addTopic = basic::SerializationActions<M>::template addConstTopic<InputDataPOCO>("input.data");

// 两个 publisher，协议包装分别是 protobuf 和"无包装"（直接 CBOR）
auto publisherSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<basic::proto_interop::Proto, InputDataPOCO>(
        r, "input data publisher", "zeromq://localhost:12345"
    );
auto publisherSink2 = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<std::void_t, InputDataPOCO>(
        r, "input data publisher 2"
        , "websocket://localhost:56789:::/data[ignoreTopic=true]"
    );

auto toPub = r.execute("addTopic", addTopic, r.importItem("source", source));
r.connect(toPub.clone(), publisherSink);
r.connect(toPub.clone(), publisherSink2);
```

### 订阅端：直接订阅

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:79–88`（已简化）

```cpp
auto heartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r
        , "heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.plain_executables.#.heartbeat"
    );
```

### 订阅端：心跳驱动的服务发现

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:90–99`（已简化）

```cpp
// 先拿到心跳广播源，再按"服务名"发现数据源并订阅它
auto heartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r, "heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.plain_executables.#.heartbeat"
    );

auto inputDataSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::setupBroadcastListenerThroughHeartbeat<InputData>(
        r
        , heartbeatSource.clone()
        , std::regex("simple_demo DataSource")   // 按服务名正则匹配
        , "input data publisher"                 // 广播源查找名
        , "input.data"                           // topic
        , "inputDataSourceComponents"            // 节点名前缀
    );
```

心跳消息里携带了发布者的**信道描述与 topic**，因此订阅端不需要硬编码数据源地址——数据源换了端口，订阅端自动跟上。

### 批量订阅

来源：`tm_examples/simple_demo/client/data_display/DataDisplayFlow.hpp:27`（已简化）

```cpp
auto sources = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::template setupBroadcastListeners<transport::HeartbeatMessage>(
        r
        , std::tuple {
            transport::MultiTransportBroadcastListenerSpec<transport::HeartbeatMessage> {
                "heartbeatListener"
                , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
                , std::nullopt
            }
        }
        , "heartbeat"
    );
// sources 是 std::tuple<Sourceoid<HeartbeatMessage>>
```

## 实时 / 回测行为差异

广播是**纯实时概念**：

| 维度 | 实时 | 回测 |
|---|---|---|
| `oneBroadcastListener` / `oneBroadcastPublisher` | 建立真实网络连接，后台线程接收/发送 | **不可用**——底层节点硬编码 `RealTimeApp<Env>` |
| 数据来源 | 网络推送 | 文件 importer（CSV / HDF5 / `ByteDataWithTopicRecordFile`）或 chain 回放 |
| topic | 网络协议级过滤（broker 端完成） | 由文件格式自带的 topic 字段承载 |
| 服务发现 | 心跳广播 + `setupBroadcastListenerThroughHeartbeat` | 无对应机制；配置在回测程序中直接写死 |
| 线程 | 每个订阅/发布各有一条后台线程（`env->multicast_threadHandles()` 等可枚举） | 单线程 |

回测中要复用实时业务逻辑，做法是把广播源作为参数注入业务组合模板：实时传网络 `Source`，回测传文件 `Source`。参见 `tm_examples/simple_demo/` 的 `MainLogicCombination`。

## 易错点

**1. publisher 的 Sink 类型是 `TypedDataWithTopic<T>`，不是 `T`**

`oneBroadcastPublisher<T>` 返回 `Sink<basic::TypedDataWithTopic<T>>`（`MultiTransportBroadcastPublisherManagingUtils.hpp:34`）。直接 `r.connect(r.actionAsSource(someAction<T>), publisherSink)` 会编译失败。必须先经过 `addConstTopic`（固定 topic）或 `addTopic`（从数据里取 topic）。

**2. `oneBroadcastListener` 抛异常，`setupBroadcastListeners` 静默跳过**

如果信道字符串来自配置文件或命令行，用 `oneBroadcastListener` 会在配置写错时直接抛异常终止程序；用 `setupBroadcastListeners` 则会跳过该路，返回的元组里对应 `Sourceoid` 永远不产生数据。两种行为各有适用场景，别混用。

**3. `topicDescription` 在不同传输上语义不同，但 `#` 会被自动转换**

框架把 `#` 统一当"多级通配"处理：RabbitMQ 原样保留，Redis/NATS 转成 `*`。但**单级通配符 `*` 的语义在各传输上并不一致**（AMQP 的 `*` 匹配一级，Redis 的 `*` 匹配任意字符序列）。需要精确过滤时，请针对目标传输书写 topic，不要指望一份 topic 在所有传输上都精确等价。

**4. `control("stop")` 之后的订阅需要 `control("restart")` 才能恢复**

`MultiTransportBroadcastListener::control` 在收到 `"stop"` 时把当前订阅存入 `restartInfo_` 并全部取消（`MultiTransportBroadcastListener.hpp:1061`）。**若在 stop 与 restart 之间又新增了订阅，那些新订阅不会进 `restartInfo_`**——因为 `restartInfo_` 只在 stop 时填充。需要动态增删订阅请直接用 `AddSubscription`/`RemoveSubscription` 指令。

**5. `threaded=true` 会插入额外的命名节点，节点名冲突会报错**

`threaded=true` 时内部注册 `name+":threadWrapper"`（`MultiTransportBroadcastPublisherManagingUtils.hpp:59`）。同一 `r` 上若已有同名节点，`registerAction` 会失败。给 publisher 起名时保证全局唯一。

**6. `oneBroadcastPublisher` 对不可直接序列化类型自动套 CBOR，可能与对端协议不符**

`oneBroadcastPublisher<T>` 在 `DirectlySerializableChecker<T>::IsDirectlySerializable()` 为 false 时自动改用 `CBOR<T>`（`MultiTransportBroadcastPublisherManagingUtils.hpp:36`）。如果对端期待的是 Proto 或 Json 编码，收到的是 CBOR，会解析失败。需要明确 wire 协议时请用 `oneBroadcastPublisherWithProtocol<Proto, T>` 或 `<Json, T>`。

**7. `fetchTypedFirstUpdateAndDisconnect` 返回 `future`，不 `get()` 就永远不会连接**

该函数（`MultiTransportBroadcastListenerManagingUtils.hpp:921`）返回 `std::future`，真正的连接动作在异步任务中执行。若拿到 future 后既不 `get()` 也不 `wait()`，程序可能在连接建立前就退出。此外，若 `predicate` 永不满足，future 永不就绪——**必须保证有超时或谓词一定可满足**。

**8. 心跳订阅本身也要占一条信道**

`setupBroadcastListenerThroughHeartbeat` 依赖一个已经建立的 `heartbeatSource`。忘记先建心跳订阅（或用错了 topic），会导致服务发现永远返回空结果，表现为"订阅建立了但收不到数据"。

## 第三方依赖

广播的第三方依赖由**具体的传输实现**决定，头文件本身通过 `MultiTransportBroadcastListener.hpp:9–21` 引入全部传输组件：

| 头文件 | 第三方库 | pkg-config |
|---|---|---|
| `multicast/MulticastComponent.hpp` | 无（POSIX socket） | —— |
| `rabbitmq/RabbitMQComponent.hpp` | rabbitmq-c | `librabbitmq` |
| `redis/RedisComponent.hpp` | hiredis | `hiredis` |
| `nats/NATSComponent.hpp` | libnats | `libnats_static` |
| `zeromq/ZeroMQComponent.hpp` | libzmq + cppzmq | `libzmq`, `cppzmq` |
| `nng/NNGComponent.hpp` | nngpp | `nngpp` |
| `shared_memory_broadcast/SharedMemoryBroadcastComponent.hpp` | Boost.Interprocess | `boost` |
| `websocket/WebSocketComponent.hpp` | IXWebSocket | `ixwebsocket` |
| `singlecast/SinglecastComponent.hpp` | Boost.Asio | `boost` |

此外 `MultiTransportBroadcastListenerManagingUtils.hpp` 引入 `basic/AppRunnerUtils.hpp` 与 `basic/WrapFacilitioidConnectorForSerialization.hpp`，而 `MultiTransportBroadcastPublisherManagingUtils.hpp:17` 额外引入后者用于协议包装。

官方文档：RabbitMQ-C https://github.com/alanxz/rabbitmq-c · hiredis https://github.com/redis/hiredis · libnats https://github.com/nats-io/nats.c · ZeroMQ https://zeromq.org/ · nngpp https://github.com/nanomsg/nngpp · IXWebSocket https://github.com/machinezone/IXWebSocket

## 相关章节

- [tm_transport 概览](00-overview.md) — 信道字符串语法、能力矩阵、`AllNetworkTransportComponents`
- [远程设施](02-facilities.md) — 有响应的通信模式；`setupOneNonDistinguishedRemoteFacility` 同样依赖心跳
- [心跳与告警](05-heartbeat-and-alert.md) — `HeartbeatMessage` 结构与 `initializeHeartbeatAndAlertComponent` / `attachHeartbeatAndAlertComponent`
- [安全与身份校验](06-security.md) — `UserToWireHook` / `WireToUserHook` 的构造与使用
- [各传输详解](03-transports/) — 每个传输的 locator 语法与能力
- [序列化格式](../tm_basic/03-serialization.md) — `TypedDataWithTopic`、`ByteDataWithTopic`、协议包装器
- [CommonFlowUtils](../tm_basic/05-common-flow-util.md) — `idFunc`，`threaded=true` 时内部使用
