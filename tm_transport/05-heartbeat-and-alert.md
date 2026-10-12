---
title: 心跳与告警
library: tm_transport
headers: [tm_kit/transport/HeartbeatAndAlertComponent.hpp, tm_kit/transport/HeartbeatMessage.hpp, tm_kit/transport/AlertMessage.hpp, tm_kit/transport/AlertEnhancedLoggingComponent.hpp, tm_kit/transport/HeartbeatMessageToRemoteFacilityCommand.hpp, tm_kit/transport/MultiTransportTouchups.hpp]
keywords: [HeartbeatAndAlertComponent, HeartbeatMessage, AlertMessage, initializeHeartbeatAndAlertComponent, attachHeartbeatAndAlertComponent, sendAlert, setStatus, publishHeartbeat, addBroadcastChannel, addFacilityChannel, addExtraHeartbeatHandler, sendCustomMessage, HeartbeatAndAlertComponentTouchupParameters, HeartbeatAndAlertComponentTouchup, PublisherTouchup, PublisherTouchupSpec, ListenerTouchup, ListenerTouchupSpec, HeartbeatDirectedListenerTouchup, HeartbeatDirectedListenerTouchupSpec, multi_transport_touchups, AlertEnhancedLoggingComponent, 心跳, 告警, 服务发现, 服务状态]
---

# 心跳与告警

## 用途

心跳是 TM Kit **服务发现**的基础设施：每个进程周期性广播一条 `HeartbeatMessage`，里面包含自己的身份、状态，以及**它对外暴露的广播信道与 facility 信道清单**。

订阅方拿到心跳后就能知道"谁在线、它提供什么服务、通过什么地址访问"，从而：

- 用 `setupBroadcastListenerThroughHeartbeat` 自动订阅远端广播
- 用 `setupOneNonDistinguishedRemoteFacility` 自动发现并连接远端 facility
- 监控整个系统的存活状态

告警是同一组件的另一半：`sendAlert` 把业务事件以 `AlertMessage` 形式广播出去，`setStatus` 更新自身在心跳里报告的健康状态。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/HeartbeatAndAlertComponent.hpp>
#include <tm_kit/transport/HeartbeatMessage.hpp>
#include <tm_kit/transport/AlertMessage.hpp>
#include <tm_kit/transport/AlertEnhancedLoggingComponent.hpp>
#include <tm_kit/transport/MultiTransportTouchups.hpp>

namespace dev::cd606::tm::transport
```

## 核心类型与签名

### 1. `HeartbeatMessage`（`HeartbeatMessage.hpp:12`）

```cpp
class HeartbeatMessage {
public:
    enum class Status { Good, Warning, Bad, Unknown };          // :15

    struct OneItemStatus {                                       // :21
        Status status;
        std::string info;
    };

    static std::string statusString(Status);                     // :25
    static Status parseStatus(std::string const &);               // :26

    HeartbeatMessage(
        std::string uuidStr
        , std::chrono::system_clock::time_point heartbeatTime
        , std::string const &host
        , int64_t pid
        , std::string const &senderDescription                      // 服务名，客户端用正则匹配它
        , std::map<std::string, std::vector<std::string>> &&broadcastChannels
        , std::map<std::string, std::string> &&facilityChannels
        , std::map<std::string, OneItemStatus> const &details = {}
    );

    void SerializeToString(std::string *s) const;                   // :60
    bool ParseFromString(std::string const &s);                     // :61

    std::string const &uuidStr() const;                             // :63
    std::chrono::system_clock::time_point heartbeatTime() const;    // :66
    std::string const &host() const;                                // :69
    int64_t pid() const;                                            // :72
    std::string const &senderDescription() const;                   // :75
    std::map<std::string,std::vector<std::string>> const &broadcastChannels() const;  // :78
    std::map<std::string,std::string> const &facilityChannels() const;                // :81
};
```

`broadcastChannels` 的值是 `vector<string>` ——**同一个名字可以对应多个信道**（同一份数据同时发到 ZeroMQ 和 WebSocket，就是示例 `DataSource.cpp` 的做法）。这正是 [ZeroMQ 传输](03-transports/zeromq.md) 里客户端取 `front()` 的原因。

`facilityChannels` 的值是单个 `string`——一个设施名对应一个信道。

### 2. `HeartbeatAndAlertComponent`（`HeartbeatAndAlertComponent.hpp:34`）

Environment 组件。同时是**日志组件**（通过 `AlertEnhancedLoggingComponent` 接入 `infra::LogLevel`）。

```cpp
class HeartbeatAndAlertComponent {
public:
    void assignIdentity(HeartbeatAndAlertComponent &&);                  // :45
    void addBroadcastChannel(std::string const &name, std::string const &channel);  // :46
    void addFacilityChannel(std::string const &name, std::string const &channel);   // :47
    void setStatus(std::string const &itemDescription, HeartbeatMessage::Status status
        , std::string const &info = "");                                 // :48
    void sendAlert(std::string const &alertTopic, infra::LogLevel level
        , std::string const &message);                                   // :49
    void publishHeartbeat(std::string const &heartbeatTopic);            // :50
    void addExtraHeartbeatHandler(std::function<void(HeartbeatMessage &&)> handler);  // :51

    template <class T>
    void sendCustomMessage(std::string const &messageTopic, T &&t);      // :53
};
```

`sendCustomMessage<T>` 允许在心跳之外广播自定义的周期性消息（如"当前持仓"），消息内容由模板类型决定。

### 3. 初始化：`initializeHeartbeatAndAlertComponent`

```cpp
// :243 — 显式给出连接类型 + locator
template <class Env>
inline void initializeHeartbeatAndAlertComponent(
    Env *env
    , std::string const &identity                 // 服务名，写进 senderDescription
    , MultiTransportBroadcastListenerConnectionType connType
    , ConnectionLocator const &locator
    , std::optional<UserToWireHook> hook = std::nullopt
);

// :338 — 用信道描述字符串（推荐）
template <class Env>
inline void initializeHeartbeatAndAlertComponent(
    Env *env
    , std::string const &identity
    , std::string const &channelDescriptor
    , std::optional<UserToWireHook> hook = std::nullopt
);
```

内部按 `connType` 分发到 `HeartbeatAndAlertComponentInitializer<Env, Component>` 的特化（`:77` 起，为 multicast / RabbitMQ / ZeroMQ / Redis / NATS / NNG / shared_memory_broadcast / WebSocket 各有特化）。**环境里没有对应组件时抛 `std::runtime_error`**（如 `:257`："connection type Multicast not supported in environment"）。

`identity` 就是 `senderDescription`——**客户端用正则匹配这个字符串来发现服务**。

### 4. 挂到图上：`attachHeartbeatAndAlertComponent`

```cpp
// :352
template <class R, std::enable_if_t<
    std::is_base_of_v<HeartbeatAndAlertComponent, typename R::EnvironmentType>
    && std::is_base_of_v<basic::real_time_clock::ClockComponent, typename R::EnvironmentType>
    , int> = 0>
void attachHeartbeatAndAlertComponent(
    R &r
    , typename R::EnvironmentType *env
    , std::string const &heartbeatTopic
    , std::chrono::system_clock::duration period
    , std::chrono::system_clock::duration furthestPoint = std::chrono::hours(24)
);
```

内部创建一个 `ClockImporter`（节点名 `"__heartbeat_clock_importer"`，`:368`）周期性地调用 `publishHeartbeat(heartbeatTopic)`（通过导出器 `"__heartbeat_run_heartbeat"`，`:371`）。

**约束**：`R::EnvironmentType` 必须同时满足 `is_base_of_v<HeartbeatAndAlertComponent, ...>` 与 `is_base_of_v<basic::real_time_clock::ClockComponent, ...>`——**心跳只能在实时 App 上用**（需要真实时钟）。

### 5. `AlertMessage`

`AlertMessage.hpp` 定义告警消息结构。告警通过 `env->sendAlert(topic, level, message)` 发出，`level` 用 `infra::LogLevel`。

`AlertEnhancedLoggingComponent`（`AlertEnhancedLoggingComponent.hpp`）把 `HeartbeatAndAlertComponent` 接入 `tm_basic` 的日志体系——于是 `env->log(infra::LogLevel::Error, "...")` 会**同时**写日志和发告警。

### 6. Touchup 辅助类

"touchup" 是延迟到 `AppRunner::finalize()` 阶段执行的图修补回调（见 [tm_infra/05-app-runner.md](../tm_infra/05-app-runner.md) 的 `addTouchup`）。这里有两组与心跳/传输相关的 touchup 辅助，用途完全不同，**别混淆**：

#### 6.1 `HeartbeatAndAlertComponentTouchup`（在 `HeartbeatAndAlertComponent.hpp:384`，**不在** `MultiTransportTouchups.hpp`）

把"初始化 + 挂载心跳"两件事合并成一次 RAII 调用：

```cpp
// tm_kit/transport/HeartbeatAndAlertComponent.hpp:377
struct HeartbeatAndAlertComponentTouchupParameters {
    std::string channelDescriptor;                              // 心跳信道
    std::string topic;                                          // 心跳 topic
    std::string identity;                                       // 服务名
    std::chrono::system_clock::duration period;                 // 心跳周期
    std::string overallStatusEntry = "";                        // 汇总状态条目的名字
    std::chrono::system_clock::duration finishAfter = std::chrono::hours(24);  // ← 注意
};

template <class R>
struct HeartbeatAndAlertComponentTouchup {
    HeartbeatAndAlertComponentTouchup(R &r, HeartbeatAndAlertComponentTouchupParameters const &param);
};
```

构造即完成 `initializeHeartbeatAndAlertComponent` + `attachHeartbeatAndAlertComponent`。**注意 `finishAfter` 默认 `std::chrono::hours(24)`**（`:383`）——与 `attachHeartbeatAndAlertComponent` 的 `furthestPoint` 是同一个 24 小时陷阱（见上文易错点 5）。注意三个必填字段（`channelDescriptor` / `topic` / `identity`）任一为空时**直接静默返回**，什么都不做（`:390`-`:394`）。

#### 6.2 `MultiTransportTouchups.hpp` 的三个 Touchup（namespace `multi_transport_touchups`）

这组是把"创建传输节点 + 接到全图"合并成一条语句的 RAII 辅助。核心手法是 `AppRunner` 的批量连接 API（见 [tm_infra/05-app-runner.md](../tm_infra/05-app-runner.md)）：

| 类型 | 行号 | 作用 |
|---|---|---|
| `PublisherTouchup<R,T>` | `:18` | 创建 `oneBroadcastPublisher<T>`，再 `connectTypedSinkToAllNodes<TypedDataWithTopic<T>>`——**把全图所有类型为 `T` 的数据都发布出去** |
| `PublisherTouchupWithProtocol<R,ProtocolWrapper,T>` | `:51` | 同上，带协议包装 |
| `PublisherTouchup<R,basic::ByteData>` | `:34` | `ByteData` 特化（空实现） |
| `ListenerTouchup<R,T>` | `:97` | 创建 `oneBroadcastListener<T>`（或 `...WithTopic`），再 `connectSourceToAllUnusedSinks<T>`——**把订阅到的数据喂给全图所有还没连的输入** |
| `HeartbeatDirectedListenerTouchup<R,T>` | `:158` | 前两者的结合：先建心跳订阅，再 `setupBroadcastListenerWithTopicThroughHeartbeat<T>` 按服务名发现远端，最后 `connectSourceToAllUnusedSinks` |

配套的 Spec 结构：

```cpp
// :10
struct PublisherTouchupSpec {
    std::string channelSpec;
    std::optional<UserToWireHook> hook = std::nullopt;
    bool threaded = false;
    std::string publisherName = "";     // 留空则用 "__publisher_touchup_" + typeid(T).name()
};

// :89
struct ListenerTouchupSpec {
    std::string channelSpec;
    bool withTopic = true;
    std::optional<std::string> topicDescription = std::nullopt;
    std::optional<WireToUserHook> hook = std::nullopt;
};

// :149
struct HeartbeatDirectedListenerTouchupSpec {
    ListenerTouchupSpec heartbeatSpec;
    std::regex serverNameRE;
    std::string broadcastSourceLookupName;
    std::string broadcastTopic;
    bool withTopic = true;
    std::optional<WireToUserHook> hook = std::nullopt;
};
```

用法（构造即生效）：

```cpp
// 来源：tm_kit/transport/MultiTransportTouchups.hpp:18、:97 的签名（示例代码库中暂无用例）
// 把图里所有 TickData 都录到 ZeroMQ 上
transport::multi_transport_touchups::PublisherTouchup<R, TickData> pubTouchup(
    r, { .channelSpec = "zeromq://localhost:12345" }
);

// 把某个信道上的 TickData 喂给图里所有还没接的 TickData 消费者
transport::multi_transport_touchups::ListenerTouchup<R, TickData> subTouchup(
    r, { .channelSpec = "zeromq://localhost:12345" }
);
```

**`PublisherTouchup` 的 `T` 是裸类型 `T`**，内部自动加 `TypedDataWithTopic<T>` 包装；`ListenerTouchup` 的 `withTopic` 为 `true` 时产出 `TypedDataWithTopic<T>`，为 `false` 时产出裸 `T`。`T = basic::ByteData` 时 `ListenerTouchup` 会插一个转换节点，把 `TypedDataWithTopic<ByteData>` 转成 `ByteDataWithTopic`（`:161`-`:172`）。

### 7. `HeartbeatMessageToRemoteFacilityCommand`

`HeartbeatMessageToRemoteFacilityCommand.hpp` 把心跳消息转换成远程设施管理指令——这是"客户端从心跳中自动建立 facility 连接"的实现细节。

## 最小可用示例

### 服务端：初始化 + 定期发布心跳

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:63–98`（已简化）

```cpp
TheEnvironment env;

// 1) 初始化：服务名 "simple_demo DataSource"，心跳信道走 RabbitMQ
transport::initializeHeartbeatAndAlertComponent(
    &env
    , "simple_demo DataSource"
    , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
);
env.setStatus("program", transport::HeartbeatMessage::Status::Good);

using R = infra::AppRunner<M>;
R r(&env);

// 2) 注册广播/设施信道（会随心跳广播出去，供客户端发现）
auto publisherSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<basic::proto_interop::Proto, InputDataPOCO>(
        r, "input data publisher", "zeromq://localhost:12345"
    );
// ... 连接 ...

// 3) 挂到图上：每 10 秒发一次心跳，topic 带服务名
transport::attachHeartbeatAndAlertComponent(
    r, &env, "simple_demo.plain_executables.data_source.heartbeat", std::chrono::seconds(10)
);

r.finalize();
```

心跳的 topic 里带上服务名（这里是 `data_source`），客户端就能按 `simple_demo.plain_executables.#.heartbeat` 订阅到所有服务的全部心跳。

### 客户端：订阅心跳并发现服务

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:79–99`（已简化）

```cpp
// 1) 订阅所有服务的心跳
auto heartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r
        , "heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.plain_executables.#.heartbeat"
    );

// 2) 按服务名正则发现数据源，自动订阅它声明的广播信道
auto inputDataSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::setupBroadcastListenerThroughHeartbeat<InputData>(
        r
        , heartbeatSource.clone()
        , std::regex("simple_demo DataSource")     // 匹配 HeartbeatMessage::senderDescription
        , "input data publisher"                   // 匹配 addBroadcastChannel 注册的名字
        , "input.data"                             // topic
        , "inputDataSourceComponents"
    );

// 3) 按服务名正则发现计算服务，自动建立在 线 facility 连接
auto calc = transport::MultiTransportRemoteFacilityManagingUtils<R>
    ::setupOneNonDistinguishedRemoteFacility<CalculateCommand, CalculateResult>(
        r
        , heartbeatSource.clone()
        , std::regex("simple_demo plain Calculator")
        , "calculator facility"
    ).facility;
```

## 实时 / 回测行为差异

心跳是**纯实时概念**：

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ —— `attachHeartbeatAndAlertComponent` 要求 `basic::real_time_clock::ClockComponent`（`HeartbeatAndAlertComponent.hpp:352` 的 `enable_if`），回测时钟不满足 |
| 服务发现 | 心跳驱动，动态 | 配置写死（直接传固定的信道字符串给 `setupSimpleRemoteFacility`） |
| 状态上报 | `setStatus` 周期广播 | 无对应机制 |
| 告警 | `sendAlert` 广播到网络 | 通常只写日志 |

**回测的处理方式**：回测程序不初始化心跳，改为把实时阶段发现到的信道地址记录下来写进配置。`tm_examples/simple_demo/plain_executables/MainLogic.cpp:101–116` 的 `if (isReal) ... else ...` 就是这个模式——实时走服务发现，非实时直接挂本地 mock。

## 易错点

**1. 必须先 `initialize` 再 `attach`**

`initializeHeartbeatAndAlertComponent` 创建组件并把 `HeartbeatAndAlertComponent` 埋进 `env`；`attachHeartbeatAndAlertComponent` 只是在图上挂一个定时器。没初始化就 attach，`publishHeartbeat` 会因为组件内部未就绪而失败或静默无输出。

**2. `identity` 字符串就是服务发现用的匹配目标**

`initializeHeartbeatAndAlertComponent` 的 `identity` 参数写入 `HeartbeatMessage::senderDescription`。客户端用 `std::regex` 匹配它——**服务端改名字，所有客户端的正则都要跟着改**。正则里含 `.` 等特殊字符时记得转义（示例里的 `"simple_demo DataSource"` 用空格分隔正是为了避免这个问题）。

**3. `addBroadcastChannel` 的"名字"是发现键，不是信道地址**

客户端调 `setupBroadcastListenerThroughHeartbeat(..., broadcastSourceLookupName, ...)` 时传的字符串必须与服务端 `addBroadcastChannel(name, channel)` 的 `name` 完全一致。`channel` 才是实际地址。两者混淆会表现为"心跳收到了但服务发现不到"。

**4. 心跳周期决定服务下线的感知延迟**

`attachHeartbeatAndAlertComponent` 的 `period`（示例中用 10 秒）与客户端的 `ttl`（默认 3 秒）、`checkPeriod`（默认 5 秒）共同决定。**若 `period > ttl`，服务会被误判为下线**——心跳还没来得及发第二次，客户端已经认为它超时了。三个参数的合理关系是 `period < ttl`，并留出网络抖动余量。

**5. `furthestPoint` 默认 24 小时，长跑程序会停止心跳**

`attachHeartbeatAndAlertComponent` 的 `furthestPoint` 默认 `std::chrono::hours(24)`（`HeartbeatAndAlertComponent.hpp:358`），ClockImporter 在这个时间点之后不再产生事件。**连续运行超过 24 小时后心跳会静默停止**，客户端开始报告服务下线。长生命周期程序必须显式放大这个值。

**6. `attachHeartbeatAndAlertComponent` 需要实时时钟组件**

`enable_if` 要求 `R::EnvironmentType` 同时继承 `HeartbeatAndAlertComponent` 与 `basic::real_time_clock::ClockComponent`（`:352`）。用回测时钟（`single_pass_iteration_clock::ClockComponent`）会编译失败。这与"心跳是纯实时概念"一致。

**7. 心跳本身占用一条广播信道**

心跳的订阅/发布与其他广播共用传输。心跳 topic 过宽（如 `#`）会让客户端收到全系统的心跳，在高频场景下产生可观流量。用带服务名前缀的 topic 缩小范围。

**8. `setStatus` 的信息是累积的，不会自动清除**

`setStatus(itemDescription, status, info)` 按 `itemDescription` 记录状态。某次设为 `Warning` 后，若不显式设回 `Good`，心跳会一直报告 `Warning`。业务恢复后必须主动复位。

## 第三方依赖

心跳本身不引入额外的第三方库——它是 `tm_transport` 的一个普通组件，依赖所选传输的实现（见 [各传输详解](03-transports/)）。

可用于承载心跳的传输（`HeartbeatAndAlertComponentInitializer` 的特化清单，`HeartbeatAndAlertComponent.hpp:77` 起）：`multicast`、`rabbitmq`、`zeromq`、`redis`、`nats`、`nng`、`shared_memory_broadcast`、`web_socket`。

`HeartbeatMessage` 的序列化用 **CBOR**（`SerializeToString` / `ParseFromString`，`HeartbeatMessage.hpp:60`），由 `src/HeartbeatMessage.cpp` 实现。

## 相关章节

- [广播](01-broadcast.md) — `setupBroadcastListenerThroughHeartbeat` 的服务发现用法
- [远程设施](02-facilities.md) — `setupOneNonDistinguishedRemoteFacility` 依赖心跳
- [tm_transport 概览](00-overview.md) — 组件模型
- [日志](../tm_basic/04-logging.md) — `AlertEnhancedLoggingComponent` 把告警接入日志体系
- [各传输详解](03-transports/) — 心跳可用的传输及其 locator 语法
