---
title: RabbitMQ 传输
library: tm_transport
headers: [tm_kit/transport/rabbitmq/RabbitMQComponent.hpp, tm_kit/transport/rabbitmq/RabbitMQImporterExporter.hpp, tm_kit/transport/rabbitmq/RabbitMQOnOrderFacility.hpp]
keywords: [RabbitMQ, RabbitMQComponent, RabbitMQImporterExporter, RabbitMQOnOrderFacility, amq.topic, exchange, vhost, durable, auto_delete, passive, persistent, AMQP, librabbitmq, topic 通配, 消息队列]
---

# RabbitMQ 传输

## 用途

基于 AMQP 0-9-1 的消息中间件传输。**同时支持广播与 on-order facility**，是 `tm_examples/` 中使用最广的传输（心跳、配置下发、RPC 都走 RabbitMQ）。

选它的理由：需要 broker 提供持久化（`durable`）、断线重连、topic 通配订阅，或者已有 RabbitMQ 基础设施。选它的问题：多一跳 broker，延迟高于直连的 ZeroMQ。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/rabbitmq/RabbitMQComponent.hpp>
#include <tm_kit/transport/rabbitmq/RabbitMQImporterExporter.hpp>
#include <tm_kit/transport/rabbitmq/RabbitMQOnOrderFacility.hpp>

namespace dev::cd606::tm::transport::rabbitmq
```

## 核心类型与签名

### 1. `RabbitMQComponent`（`RabbitMQComponent.hpp:25`）

Environment 组件。加入 `infra::Environment<...>` 后，`tm_transport` 才知道可以在本进程建立 RabbitMQ 连接。

提供 `rabbitmq_threadHandles()`，返回 `unordered_map<ConnectionLocator, std::thread::native_handle_type>`，用于诊断（哪些连接开了后台线程）。异常类型 `RabbitMQComponentException`（`:20`）。

### 2. Locator 语法

```
rabbitmq://host:port:userName:password:exchangeName[vhost=/][durable=true][auto_delete=false][passive=false][persistent=false]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` | broker 地址 | —— |
| `port` | broker 端口（5672） | 0 → 默认 |
| `userName` / `password` | AMQP 凭据 | —— |
| `identifier` | **exchange 名**（广播）或 **RPC 队列名**（facility） | —— |
| `vhost` | AMQP virtual host | `/`（`src/rabbitmq/RabbitMQComponent.cpp:83`） |
| `passive` | 只检查队列是否存在，不创建 | `false`（`:173`） |
| `durable` | 队列/交换机持久化 | `false`（`:174`） |
| `auto_delete` | 无消费者时自动删除 | `false`（`:175`） |
| `persistent` | 消息持久化（发布侧） | `false`（`:435`） |

示例：`rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]` —— 连本机默认端口，用户/密码 `guest`/`guest`，exchange 用内置的 `amq.topic`，队列持久化。

### 3. 广播工厂：`RabbitMQImporterExporter<M>`（`RabbitMQImporterExporter.hpp:16`）

```cpp
template <class M>
class RabbitMQImporterExporter {
public:
    // :19 — 原始字节 + topic
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &exchangeLocator
        , std::string const &topic = ""
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

    // :64 — 反序列化到 T
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(
        ConnectionLocator const &exchangeLocator
        , std::string const &topic = ""
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

    // :115 / :151 — 对应导出器（第三个参数是心跳名，用于服务发现）
    static std::shared_ptr<typename M::template Exporter<basic::ByteDataWithTopic>>
    createExporter(
        ConnectionLocator const &exchangeLocator
        , std::optional<UserToWireHook> userToWireHook = std::nullopt
        , std::string const &heartbeatName = ""
    );

    template <class T>
    static std::shared_ptr<typename M::template Exporter<basic::TypedDataWithTopic<T>>>
    createTypedExporter(
        ConnectionLocator const &exchangeLocator
        , std::optional<UserToWireHook> userToWireHook = std::nullopt
        , std::string const &heartbeatName = ""
    );
};
```

exchange 类型固定为 `topic`（`src/rabbitmq/RabbitMQComponent.cpp:172`、`:200`），因此 `identifier` 指定的 exchange 必须是 topic 类型。

### 4. Facility 工厂：`RabbitMQOnOrderFacility<Env>`（`RabbitMQOnOrderFacility.hpp`）

```cpp
template <class Env>
class RabbitMQOnOrderFacility {
public:
    template <class A, class B>
    static std::shared_ptr<typename infra::RealTimeApp<Env>::template OnOrderFacility<A,B>>
    createTypedRPCOnOrderFacility(
        ConnectionLocator const &locator
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    );
};
```

facility 模式下 `identifier` 被当作 **RPC 队列名**（`src/rabbitmq/RabbitMQComponent.cpp:425`、`:580` 的 `rpcQueue_(l.identifier())`），与广播模式的 exchange 名语义不同。

## 最小可用示例

### 广播订阅（含 topic 通配）

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:79–88`

```cpp
auto heartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r
        , "heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.plain_executables.#.heartbeat"
    );
```

topic 里的 `#` 是 AMQP 的**多级**通配符（匹配零个或多个词），`*` 是**单级**通配符。框架对 RabbitMQ 的 topic **不做任何转换**（`tm_kit/transport/MultiTransportBroadcastListener.hpp:268` 的 `parseTopic`，RabbitMQ 分支在 `:285` 直接 `return s;`）。

### 发布

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:168`（已简化）

```cpp
auto publisherSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisher<basic::nlohmann_json_interop::Json<simple_demo::ConfigureResultPOCO>>(
        r
        , "configureResultPublisher"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic"
    );
```

### 服务端 facility（RPC 队列）

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:121–141`（已简化）

```cpp
transport::MultiTransportFacilityWrapper<R>::facilityWrapperWithProtocol
    <basic::proto_interop::Proto, ConfigureCommandPOCO, ConfigureResultPOCO>(
    "rabbitmq://127.0.0.1::guest:guest:test_config_queue"   // test_config_queue 是 RPC 队列名
    , "cfg_wrapper_"
)
```

## 实时 / 回测行为差异

RabbitMQ 传输**只在实时模式可用**（底层节点基于 `RealTimeApp`）。回测中：

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗（编译期即失败） |
| 数据来源 | broker 推送 | 文件 importer 或 chain 回放 |
| topic 通配 | broker 端完成过滤，客户端只收匹配的消息 | 无对应机制 |
| 持久化 | `durable=true` 时消息跨 broker 重启保留 | 不适用 |
| 服务发现 | 心跳走同一 exchange | 配置写死 |

## 易错点

**1. 广播的 `identifier` 是 exchange 名，facility 的 `identifier` 是队列名**

同一个 locator 字符串在两种角色下含义不同：广播时 `identifier` 传给 `amqp_exchange_declare`（`src/rabbitmq/RabbitMQComponent.cpp:171`），facility 时作为 `rpcQueue_`（`:425`）。用同一个 locator 同时做广播与 facility 会导致队列/exchange 命名冲突。

**2. exchange 名写错时，若 `passive=false` 会静默创建新 exchange**

默认 `passive=false`，客户端订阅一个不存在的 exchange 会**创建**它，然后永远收不到消息——不报错。排查"订阅了但没数据"时，先确认 exchange 名拼写、以及服务端用的是同一个。

**3. `durable=true` 必须在两端一致**

`durable` 影响 exchange/queue 的声明参数。客户端用 `durable=true` 而服务端用默认 `false`，AMQP 会因声明参数冲突而报错（PRECONDITION_FAILED）。所有进程必须用完全相同的 locator 属性。

**4. `amq.topic` 是 broker 内置 exchange，不能自定义参数**

`amq.*` 前缀是 RabbitMQ 保留的内置 exchange。对 `amq.topic` 传 `durable=true` 时，框架会在声明队列时用该参数（队列可以持久化），但 **exchange 本身无法重新声明**。若需要自定义 exchange 参数，用非 `amq.` 开头的名字。

**5. AMQP topic 的 `#` 与 `*` 语义与其他传输不同**

AMQP：`*` 匹配恰好一个词，`#` 匹配零个或多个词，用 `.` 分词。Redis/NATS 的分隔与通配规则不同（框架会把 `#` 转成 `*` 给它们，但 `*` 的语义并不等价）。写跨传输的 topic 时只依赖 `#` 作为多级通配。

**6. `persistent` 是发布侧属性，不是订阅侧**

`persistent=true` 在 exporter 上设置（`src/rabbitmq/RabbitMQComponent.cpp:435`）。写在订阅端的 locator 里不生效——不会被报错，只是被忽略。

**7. vhost 不在基础地址里，只能写在属性块**

AMQP 的 vhost 不是 `host:port` 的一部分，必须写 `[vhost=/myvhost]`。默认 `/`（`:83`）。多个 vhost 的环境里，忘记写 vhost 会连到 `/` 并报"exchange 不存在"。

## 第三方依赖

| 库 | 版本/包名 | 用途 | 官方文档 |
|---|---|---|---|
| rabbitmq-c | vcpkg 包 `librabbitmq`，pkg-config `librabbitmq` | AMQP 客户端 C 库 | https://github.com/alanxz/rabbitmq-c |
| OpenSSL | 由 rabbitmq-c 传递依赖 | TLS（`TLSClientConfigurationComponent`） | https://www.openssl.org/ |

`tm_transport/meson.build:5` 声明 `rabbitmq_dep = dependency('librabbitmq')`。

## 相关章节

- [广播](../01-broadcast.md) — `oneBroadcastListener` / `oneBroadcastPublisher` 的通用用法
- [远程设施](../02-facilities.md) — `setupOneNonDistinguishedRemoteFacility` 等
- [各传输能力矩阵](../00-overview.md) — 与其他传输的对比
- [心跳与告警](../05-heartbeat-and-alert.md) — 心跳默认就跑在 RabbitMQ 上
- [tm_transport 概览](../00-overview.md) — locator 与 channel spec 语法
