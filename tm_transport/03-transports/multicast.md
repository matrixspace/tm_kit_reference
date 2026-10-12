---
title: Multicast 传输
library: tm_transport
headers: [tm_kit/transport/multicast/MulticastComponent.hpp, tm_kit/transport/multicast/MulticastImporterExporter.hpp]
keywords: [multicast, MulticastComponent, MulticastImporterExporter, UDP 组播, 网卡, interface, envelop, ignoreTopic, 同网段, 无 broker, 行情分发]
---

# Multicast 传输

## 用途

基于 **UDP 组播**的广播传输。一个 sender 往组播地址发一份数据，同网段内所有加入该组的接收者都能收到。

适合：局域网内的高频行情分发（一份数据同时到达多台机器，延迟一致）、无需 broker 的简单一对多。

不适合：跨网段（需要路由器支持组播）、需要可靠送达（UDP 无重传）、需要历史补发。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/multicast/MulticastComponent.hpp>
#include <tm_kit/transport/multicast/MulticastImporterExporter.hpp>

namespace dev::cd606::tm::transport::multicast
```

## 核心类型与签名

### 1. `MulticastComponent`（`MulticastComponent.hpp:22`）

Environment 组件。提供 `multicast_threadHandles()` 用于诊断，以及 `struct NoTopicSelection {}` 用于 topic 参数。

### 2. Locator 语法

```
multicast://groupAddress:port[envelop=cbor][ignoreTopic=false][interface=eth0]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` | 组播组地址（如 `239.255.0.1`） | —— |
| `port` | 端口 | —— |
| `identifier` | 未使用 | —— |
| `envelop` | topic 编码方式 | `cbor`（`src/multicast/MulticastComponent.cpp:537`） |
| `ignoreTopic` | 为 `true` 时把信封强制为 `binary`（不带 topic） | `false`（`:538`） |
| `interface` | 指定发送/接收网卡 | `""`（由系统路由决定，`:541`） |

`envelop` 的取值（`src/multicast/MulticastComponent.cpp:24` 的 `parseEncodingChoice`）：

| 取值 | 含义 |
|---|---|
| `"cbor"`（或其他任意值） | 用 CBOR 编码 topic 信封 |
| `"binary"` / `"raw-binary"` | 纯二进制，无 topic |
| `"binary-adhoc"` | 另一种二进制信封格式 |

### 3. 工厂：`MulticastImporterExporter<M>`（`MulticastImporterExporter.hpp:18`）

```cpp
template <class M>
class MulticastImporterExporter {
public:
    // :21 / :66
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<MulticastComponent::NoTopicSelection, std::string, std::regex> const &topic
            = MulticastComponent::NoTopicSelection()
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(...);

    // :117 / :159 — 导出器；heartbeatName 用于服务发现
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

同一 `host:port` 只建立一个底层订阅（`src/multicast/MulticastComponent.cpp:533` 的 `subscriptions_` 按 `ConnectionLocator{host,port}` 索引，**忽略属性**），多个 topic 过滤条件挂在同一订阅上。

### 4. 原生不支持 on-order facility，但可用合成设施绕过

组播本身是单向的，没有请求-响应语义。`MultiTransportRemoteFacilityConnectionType` 中没有 multicast 项（`tm_kit/transport/MultiTransportRemoteFacility.hpp:41`），所以 `setupSimpleRemoteFacility("multicast://...")` 会失败。

但 `SyntheticMultiTransportFacility` 可以在组播上**合成** facility——开请求、响应两条组播信道，用应用层逻辑配对（`tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:292`）。见 [远程设施](../02-facilities.md)。

## 最小可用示例

`tm_examples/` 中暂无 multicast 的直接用例。以下为按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/multicast/MulticastImporterExporter.hpp:21 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::multicast::MulticastComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;
using R = infra::AppRunner<M>;

// 发布：向组播组 239.255.0.1:12345 发送 TickData
auto publisher = transport::multicast::MulticastImporterExporter<M>
    ::template createTypedExporter<TickData>(
        transport::ConnectionLocator::parse("239.255.0.1:12345"),
        std::nullopt,          // userToWireHook
        "tick publisher"       // heartbeatName
    );

// 订阅：只接收 topic 为 "tick.btc" 的消息
auto subscriber = transport::multicast::MulticastImporterExporter<M>
    ::template createTypedImporter<TickData>(
        transport::ConnectionLocator::parse("239.255.0.1:12345"),
        std::string("tick.btc"),
        std::nullopt
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | 组播网络推送 | 文件 importer |
| 可靠性 | UDP，可能丢包/乱序 | 文件中数据完整有序 |
| topic 过滤 | 应用层（收到后按 envelop 解析 topic 再过滤） | 文件格式自带 topic |
| 网卡选择 | `interface` 属性 | 不适用 |

**关键含义**：组播是 UDP，**没有重传**。用它做实时行情分发时，丢包会直接表现为数据缺口。回测中要复现同样场景，需要把实时收到的数据落盘（这时落盘的已经是"丢过包"的数据），或从交易所的原始数据重建。

## 易错点

**1. 组播地址必须在合法范围内**

`host` 必须是 D 类地址（`224.0.0.0`–`239.255.255.255`）。写成普通 IP（如 `192.168.1.1`）不会报错，但底层 socket 加入组播组会失败。

**2. `ignoreTopic=true` 会强制把 `envelop` 覆盖为 `binary`**

`src/multicast/MulticastComponent.cpp:538` 明确：`ignoreTopic` 为 true 时 `choice` 被**重新赋值**为 `Binary`，覆盖你写的 `envelop`。也就是说订阅端用 `ignoreTopic=true` 而发布端用默认 `envelop=cbor` 时，接收方会按纯二进制解析带 CBOR 信封的数据，得到乱码。

**3. 多网卡机器必须指定 `interface`**

`interface` 默认为空串（`:541`），由系统路由决定用哪块网卡。多网卡（如同时接行情网和办公网）的机器上，不指定 `interface` 可能发到错误的网卡，表现为"同网段的其他机器收不到"。

**4. 同一 `host:port` 的多个订阅共享一个底层 socket，但属性不同不会分别生效**

`subscriptions_` 的 key 是 `ConnectionLocator{host, port}`（`:533`），**不含属性**。第一次建立订阅时用的 `envelop`/`interface` 决定了整个 socket 的行为；后续对同一 `host:port` 用不同 `envelop` 再订阅，不会重建 socket。要避免这一点，请对同一组播组的所有订阅使用一致的属性。

**5. 跨网段需要路由器支持**

组播默认不跨网段。跨机房/跨子网使用需要网络设备配置 IGMP 与组播路由，否则发送方正常、接收方永远收不到，且无任何错误提示。

**6. 原生不支持 facility**

组播是单向的。需要请求-响应请用 `socket_rpc`、`grpc_interop`、RabbitMQ 等，或用 `SyntheticMultiTransportFacility` 在组播上合成（注意它没有寻址与派发，所有响应对所有监听者可见）。

## 第三方依赖

无额外第三方库——基于 **Boost.Asio** 的 UDP socket 实现（`tm_transport/meson.build` 的 `boost_dep`）。

Boost.Asio 官方文档：https://www.boost.org/doc/libs/release/doc/html/boost_asio.html

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口
- [singlecast 传输](singlecast.md) — UDP 单播版本
- [ZeroMQ 传输](zeromq.md) — 另一种无 broker 的一对多方案（TCP）
- [各传输能力矩阵](../00-overview.md)
