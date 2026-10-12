---
title: Singlecast 传输
library: tm_transport
headers: [tm_kit/transport/singlecast/SinglecastComponent.hpp, tm_kit/transport/singlecast/SinglecastImporterExporter.hpp]
keywords: [singlecast, SinglecastComponent, SinglecastImporterExporter, UDP 单播, 点对点, envelop, ignoreTopic, 无 broker]
---

# Singlecast 传输

## 用途

基于 **UDP 单播**的广播传输：发送方把数据发到一个确定的 `host:port`，只有一个接收者能收到。

与 [multicast](multicast.md) 的差别只有一个：目的地址是普通单播地址而非组播组。因此它**不依赖网络设备支持组播**，可以跨网段使用（只要有路由）。仍然是 UDP——无重传、无保序。

适合：跨网段的轻量状态推送、点对点的低延迟通知。不适合：需要可靠送达或需要多订阅者的场景。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/singlecast/SinglecastComponent.hpp>
#include <tm_kit/transport/singlecast/SinglecastImporterExporter.hpp>

namespace dev::cd606::tm::transport::singlecast
```

## 核心类型与签名

### 1. `SinglecastComponent`（`SinglecastComponent.hpp`）

Environment 组件。提供 `singlecast_threadHandles()` 用于诊断，以及 `struct NoTopicSelection {}`。

### 2. Locator 语法

```
singlecast://host:port[envelop=cbor][ignoreTopic=false]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` | 目的地址。订阅端忽略此字段，固定监听 `0.0.0.0`（`src/singlecast/SinglecastComponent.cpp:167`） | —— |
| `port` | 端口（必填） | —— |
| `identifier` | 未使用 | —— |
| `envelop` | topic 编码方式 | `cbor`（`:344`、`:389`） |
| `ignoreTopic` | 为 `true` 时按纯二进制解析（不带 topic） | `false` |

`envelop` 的取值与 multicast 相同（`src/singlecast/SinglecastComponent.cpp:18` 的 `parseEncodingChoice`）：`"cbor"` / `"binary"` / `"raw-binary"` / `"binary-adhoc"`，其他值回落到 CBOR。

发送端用 `locator.host()` 解析目的地址（`:282`），接收端固定绑定 `0.0.0.0:port` 不区分来源（`:167`）。

### 3. 工厂：`SinglecastImporterExporter<M>`（`SinglecastImporterExporter.hpp:18`）

```cpp
template <class M>
class SinglecastImporterExporter {
public:
    // :21 / :66
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<SinglecastComponent::NoTopicSelection, std::string, std::regex> const &topic
            = SinglecastComponent::NoTopicSelection()
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(...);

    // :117 / :153
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

### 4. 不支持 on-order facility

`MultiTransportRemoteFacilityConnectionType`（`tm_kit/transport/MultiTransportRemoteFacility.hpp:41`）中没有 singlecast 项。

## 最小可用示例

`tm_examples/` 中暂无 singlecast 的直接用例。按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/singlecast/SinglecastImporterExporter.hpp:21 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::singlecast::SinglecastComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;

// 发送：UDP 单播到 192.168.1.50:12345
auto publisher = transport::singlecast::SinglecastImporterExporter<M>
    ::template createTypedExporter<StatusUpdate>(
        transport::ConnectionLocator::parse("192.168.1.50:12345"),
        std::nullopt,
        "status publisher"
    );

// 接收：绑定本机 12345 端口（locator 的 host 被忽略）
auto subscriber = transport::singlecast::SinglecastImporterExporter<M>
    ::template createTypedImporter<StatusUpdate>(
        transport::ConnectionLocator::parse("0.0.0.0:12345"),
        std::string("status.risk"),
        std::nullopt
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | UDP 单播推送 | 文件 importer |
| 可靠性 | UDP，可能丢包/乱序 | 文件完整有序 |
| 接收端绑定 | 固定 `0.0.0.0:port`，不校验来源 | 不适用 |
| topic 过滤 | 应用层 | 文件格式自带 topic |

同 multicast：**UDP 无重传**，丢包表现为数据缺口。

## 易错点

**1. 接收端的 `host` 字段被忽略**

订阅端固定绑定 `0.0.0.0:port`（`src/singlecast/SinglecastComponent.cpp:167`），locator 里写什么 host 都不影响监听地址。写 `singlecast://192.168.1.50:12345` 作为接收端不会"只接收来自该 IP 的数据"——**任何**发到本机 12345 端口的 UDP 包都会被收到。

**2. 没有来源校验，不是安全边界**

承接上一条：任何能访问到该端口的进程都能往里发数据。需要来源认证时必须叠加 identity checker 或签名 hook（见 [安全与身份校验](../06-security.md)）。

**3. `envelop` 在收发两端必须一致**

`ignoreTopic=true` 与 `envelop=cbor` 的组合语义与 multicast 一致（见 [multicast 的坑 2](multicast.md)）：一端带 CBOR 信封、另一端按纯二进制解析，会得到乱码而非报错。

**4. 不支持 facility**

需要请求-响应请用 `socket_rpc`、`grpc_interop` 或带 broker 的传输。

**5. 端口冲突静默失败**

UDP 端口被占用时绑定失败可能只体现在日志里。同一台机器上跑多个接收进程时，确认端口不重复。

## 第三方依赖

无额外第三方库——基于 **Boost.Asio** 的 UDP socket（`tm_transport/meson.build` 的 `boost_dep`）。

Boost.Asio 官方文档：https://www.boost.org/doc/libs/release/doc/html/boost_asio.html

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口
- [multicast 传输](multicast.md) — 组播版本；`envelop`/`ignoreTopic` 语义相同
- [各传输能力矩阵](../00-overview.md)

