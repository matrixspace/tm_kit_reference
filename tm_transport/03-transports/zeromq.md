---
title: ZeroMQ 传输
library: tm_transport
headers: [tm_kit/transport/zeromq/ZeroMQComponent.hpp, tm_kit/transport/zeromq/ZeroMQImporterExporter.hpp]
keywords: [ZeroMQ, ZeroMQComponent, ZeroMQImporterExporter, libzmq, cppzmq, pub sub, 直连, 无 broker, 低延迟, 行情分发]
---

# ZeroMQ 传输

## 用途

基于 ZeroMQ 的 pub/sub **直连**传输。没有 broker：publisher 直接绑定端口，subscriber 直接连接。

优势是延迟低、部署简单（不需要额外进程）。代价是：

- 没有持久化，订阅者掉线期间的消息丢失
- 没有服务端过滤——**所有消息都发到每个订阅者**，topic 过滤在客户端做
- 慢订阅者会导致队列积压（可配置水位）

行情分发是它的典型场景：一个行情源，多个策略进程，延迟敏感。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/zeromq/ZeroMQComponent.hpp>
#include <tm_kit/transport/zeromq/ZeroMQImporterExporter.hpp>

namespace dev::cd606::tm::transport::zeromq
```

## 核心类型与签名

### 1. `ZeroMQComponent`（`ZeroMQComponent.hpp:22`）

Environment 组件。提供 `zeromq_threadHandles()` 用于诊断。

### 2. Locator 语法

```
zeromq://host:port            # TCP 模式
zeromq://host:port:::identifier   # inproc / ipc 模式（identifier 作为地址）
```

`host` 字段有三类取值，决定底层 ZeroMQ 地址的构造方式（`src/zeromq/ZeroMQComponent.cpp:51`）：

| `host` 取值 | 构造出的 ZeroMQ 地址 | 说明 |
|---|---|---|
| `inproc` | `inproc://<identifier>` | 同进程内通信；`identifier` 是通道名（`:52`） |
| `ipc` | `ipc://<identifier>` | 同机进程间；`identifier` 是 socket 文件路径（`:52`） |
| 其他 | `tcp://<host>:<port>`（客户端 `connect`，`:54`）<br>`tcp://*:<port>`（服务端 `bind`，`:199`） | 网络模式；`port` 必填 |

**没有任何属性块**——ZeroMQ 传输不使用 `envelop`、`ignoreTopic`、`durable` 等属性，写进 `[...]` 不会被读取。

### 3. 工厂：`ZeroMQImporterExporter<M>`（`ZeroMQImporterExporter.hpp:18`）

```cpp
template <class M>
class ZeroMQImporterExporter {
public:
    // :21 — 原始字节 + topic
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<ZeroMQComponent::NoTopicSelection, std::string, std::regex> const &topic
            = ZeroMQComponent::NoTopicSelection()
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

    // :66 — 反序列化到 T
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(...);

    // :117 / :153 — 导出器
    static std::shared_ptr<typename M::template Exporter<basic::ByteDataWithTopic>>
    createExporter(
        ConnectionLocator const &locator
        , std::optional<UserToWireHook> userToWireHook = std::nullopt
        , std::string const &heartbeatName = ""
    );

    template <class T>
    static std::shared_ptr<typename M::template Exporter<basic::TypedDataWithTopic<T>>>
    createTypedExporter(...);
};
```

注意 `topic` 参数的类型是 `std::variant<NoTopicSelection, std::string, std::regex>`——**与 RabbitMQ/Redis 的 `std::string` 不同**。它支持三种模式（匹配实现在 `src/zeromq/ZeroMQComponent.cpp:89`、`:94`）：

- `NoTopicSelection{}` —— 不过滤，收全部
- `std::string` —— **精确相等**匹配（`data.topic == std::get<0>(f)`，`:89`），不是前缀匹配
- `std::regex` —— 正则匹配（`std::regex_match`，`:94`）

**过滤在客户端进行**，消息仍会全部到达本进程。

### 4. 不支持 on-order facility

ZeroMQ 在 `MultiTransportRemoteFacilityConnectionType` 中没有对应项（`tm_kit/transport/MultiTransportRemoteFacility.hpp:41`）。需要请求-响应请用 `socket_rpc` 或 RabbitMQ/Redis/NATS。

## 最小可用示例

### 发布

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:72–77`

```cpp
auto publisherSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<basic::proto_interop::Proto, InputDataPOCO>(
        r
        , "input data publisher"
        , "zeromq://localhost:12345"
    );
```

### 订阅

`tm_examples/` 中的订阅端不硬编码 ZeroMQ 地址，而是**从心跳里取出发布者声明的信道**再订阅。来源：`tm_examples/simple_demo/qt_client/chart/tmPart.cpp:198–204`、`:268–273`（已简化）

```cpp
// 1) 从数据源的心跳消息里取出它声明的广播信道（在 DataSource.cpp 里是 "zeromq://localhost:12345"）
auto inputDataChannelIter = firstDataSourceHeartbeat.broadcastChannels().find("input data publisher");
std::string inputDataChannel;
if (inputDataChannelIter != firstDataSourceHeartbeat.broadcastChannels().end()
    && !inputDataChannelIter->second.empty()) {
    inputDataChannel = inputDataChannelIter->second.front();
}

// 2) 用取到的信道字符串订阅——传输类型在运行期才确定
auto source = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<InputData>(
        *r
        , "inputDataListener"
        , inputDataChannel
    );
```

这正是"换传输不改代码"的体现：订阅端只知道"数据源叫 input data publisher"，至于它是 ZeroMQ 还是 RabbitMQ，由发布者的心跳决定。

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | 直连 publisher 推送 | 文件 importer / chain 回放 |
| 消息保留 | 无——订阅者不在线即丢失 | 文件中的数据完整存在 |
| topic 过滤 | **客户端**过滤（网络流量已产生） | 文件格式自带的 topic 字段 |
| 启动顺序 | publisher 必须先起（否则 subscriber 连不上） | 不适用 |

**回测的重要含义**：由于 ZeroMQ 不保留历史消息，用 ZeroMQ 录制的实时数据若想在回测中重放，必须在**实时阶段**把收到的字节流落盘（例如用 `ByteDataWithTopicRecordFileImporterExporter`），回测时再读文件。

## 易错点

**1. publisher 必须先于 subscriber 启动**

ZeroMQ 的 `bind` 在 publisher 侧，subscriber 用 `connect`。如果 subscriber 先启动，`connect` 会失败或静默重试直到 publisher 出现。程序启动顺序不确定时，会表现为"订阅端有时能收到数据有时不能"。需要可靠启动顺序时改用 RabbitMQ。

**2. topic 过滤在客户端，不减少网络流量**

`createTypedImporter` 的 `topic` 参数只影响**本进程内**是否把消息交给下游，所有消息仍然经过网络到达本进程并反序列化。高流量场景下用正则过滤不会省任何带宽。

**3. 没有属性块，写进 `[...]` 的内容会被静默忽略**

与 `websocket`/`multicast`/`singlecast` 不同（它们有 `ignoreTopic`，见 `src/websocket/WebSocketComponent.cpp:90`），ZeroMQ 的 locator 里写 `[ignoreTopic=true]` 不会报错但也不生效。

**4. `std::string` 类型的 topic 是精确匹配，不是前缀匹配**

`createTypedImporter` 传 `std::string` 时用的是 `data.topic == topic`（`src/zeromq/ZeroMQComponent.cpp:89`）。想匹配一类 topic 必须用 `std::regex`，不能用"前缀字符串"。这与 RabbitMQ（AMQP 通配）和 Redis（glob）的直觉相反，是最容易踩的坑。

**5. 慢订阅者会积压，最终可能阻塞 publisher**

ZeroMQ 的 pub socket 有高水位标记（HWM）。订阅者处理不过来时消息在 publisher 侧排队，达到 HWM 后 **publisher 会丢弃消息**（pub/sub 模式的默认行为是丢弃而非阻塞）。对可靠性要求高的场景要改用有 broker 的传输。

**6. 不支持 facility**

把 `zeromq://...` 传给 `setupSimpleRemoteFacility` 会抛异常——`parseMultiTransportRemoteFacilityChannel` 返回 `nullopt`，随后 `setupSimpleRemoteFacility` 抛 `std::runtime_error`（`tm_kit/transport/MultiTransportRemoteFacilityManagingUtils.hpp:1508`）。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| libzmq | `libzmq` | ZeroMQ 核心 C 库 | https://zeromq.org/ · https://libzmq.readthedocs.io/ |
| cppzmq | `cppzmq` | ZeroMQ 的 C++ 绑定 | https://github.com/zeromq/cppzmq |

`tm_transport/meson.build:6` 声明 `zmq_dep = [dependency('libzmq'), dependency('cppzmq')]`。

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口
- [各传输能力矩阵](../00-overview.md) — ZeroMQ 不支持 facility
- [multicast 传输](multicast.md) — 另一种无 broker 的一对多方案
- [shared_memory_broadcast 传输](shared_memory_broadcast.md) — 同机进程间无网络的方案
