---
title: WebSocket 传输
library: tm_transport
headers: [tm_kit/transport/websocket/WebSocketComponent.hpp, tm_kit/transport/websocket/WebSocketImporterExporter.hpp, tm_kit/transport/websocket/WebSocketClientFacility.hpp, tm_kit/transport/websocket/WebSocketServerFacility.hpp, tm_kit/transport/websocket/WebSocketLazyImporter.hpp]
keywords: [websocket, WebSocketComponent, WebSocketImporterExporter, WebSocketClientFacility, WebSocketServerFacility, WebSocketOnOrderFacility, ixwebsocket, IXWebSocket, ignoreTopic, binary, no_verify, useIXWebSocket, 浏览器, 双向, 前端]
---

# WebSocket 传输

## 用途

基于 WebSocket 的传输，**同时支持广播与 on-order facility**。其独特价值是**浏览器/前端可直连**——`tm_examples/simple_demo` 的 Qt 客户端、GUI 客户端都通过它接收数据。

选它的理由：需要网页或 GUI 前端接入；需要双向长连接；已有 HTTP 基础设施（可复用 80/443 端口与反向代理）。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/websocket/WebSocketComponent.hpp>
#include <tm_kit/transport/websocket/WebSocketImporterExporter.hpp>
#include <tm_kit/transport/websocket/WebSocketClientFacility.hpp>
#include <tm_kit/transport/websocket/WebSocketServerFacility.hpp>
#include <tm_kit/transport/websocket/WebSocketLazyImporter.hpp>

namespace dev::cd606::tm::transport::web_socket
```

> 注意命名空间是 `web_socket`（带下划线），而目录名是 `websocket`（无下划线）。

## 核心类型与签名

### 1. `WebSocketComponent`

Environment 组件。提供 `websocket_threadHandles()` 用于诊断。异常类型在 `WebSocketComponentException.hpp`。

### 2. Locator 语法

```
websocket://host:port:::/path[ignoreTopic=false][binary=true][useIXWebSocket=false][no_verify=false][logPerMessageCount=-1][logEveryReceivedMessage=false][wsHandshakeDoesNotUsePort=false]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` / `port` | 监听或连接地址 | —— |
| `identifier` | **URL 路径**（如 `/data`） | —— |
| `ignoreTopic` | 为 `true` 时消息不带 topic 头 | `false`（`src/websocket/WebSocketComponent.cpp:90`） |
| `binary` | 用二进制帧还是文本帧 | `true`（`:108`） |
| `useIXWebSocket` | 使用 IXWebSocket 后端（而非 Boost.Beast） | `false`（`:109`） |
| `no_verify` | 跳过 TLS 证书校验（**仅测试用**） | `false`（`:2148`） |
| `logPerMessageCount` | 每 N 条消息打一次日志，`-1` 关闭 | `-1`（`:106`） |
| `logEveryReceivedMessage` | 每条收到的消息都打日志 | `false`（`:110`） |
| `wsHandshakeDoesNotUsePort` | 握手时不在 Host 头里带端口 | `false`（`:360`） |

`ws_handshake_does_not_use_port` 是 `wsHandshakeDoesNotUsePort` 的别名写法（`:360`）。

### 3. 广播工厂：`WebSocketImporterExporter<M>`（`WebSocketImporterExporter.hpp:18`）

```cpp
template <class M>
class WebSocketImporterExporter {
public:
    // :21 / :71 — 两个 createImporter 重载（initialDataGenerator 与 initialMessage 两种形式）
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<WebSocketComponent::NoTopicSelection, std::string, std::regex> const &topic
            = WebSocketComponent::NoTopicSelection()
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
        , std::function<std::vector<basic::ByteData>()> const &initialDataGenerator = {}
        , std::function<std::optional<basic::ByteData>(basic::ByteDataView const &)> const &protocolReactor = {}
        , std::function<void()> const &protocolRestartReactor = {}
    );

    // :75 / :133
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(...);

    // :136 / :173 — 导出器；protocolReactorFactory 用于自定义握手后的协议交互
    static std::shared_ptr<typename M::template Exporter<basic::ByteDataWithTopic>>
    createExporter(
        ConnectionLocator const &locator
        , std::optional<UserToWireHook> userToWireHook = std::nullopt
        , std::string const &heartbeatName = ""
        , std::function<std::function<std::optional<basic::ByteData>(basic::ByteDataView const &, std::atomic<bool> &)>()>
            const &protocolReactorFactory = {}
    );
    template <class T>
    static std::shared_ptr<typename M::template Exporter<basic::TypedDataWithTopic<T>>>
    createTypedExporter(...);
};
```

`protocolReactor` / `protocolReactorFactory` 是 WebSocket 特有的钩子：允许在收到每条消息时决定是否回发一条原始字节消息——用于实现自定义的请求-响应子协议或心跳应答。返回 `nullopt` 表示不回。

### 4. Facility：客户端与服务端

```cpp
// WebSocketClientFacility.hpp:21
template <class Env>
class WebSocketOnOrderFacilityClient { /* ... */ };

// WebSocketServerFacility.hpp:21
template <class Env>
class WebSocketOnOrderFacility {
public:
    // :102 — 反序列化器
    static auto simplyDeserialize();
    // :109 — 校验身份后反序列化
    static auto checkIdentityAndDeserialize();
    // :139 — 按身份序列化响应
    static auto serializeBasedOnIdentity();

    // :381 起 — 完整的 wrapper 族（与 MultiTransportFacilityWrapper 对应）
    static auto facilityWrapper(...);
    static auto facilityWrapperWithoutReply(...);
    static auto localFacilityWrapper(...);
    static auto localFacilityWrapperWithoutReply(...);
    static auto facilityWithExternalEffectsWrapper(...);
    static auto facilityWithExternalEffectsWrapperWithoutReply(...);
    static auto vieFacilityWrapper(...);
    static auto vieFacilityWrapperWithoutReply(...);
};
```

`WithoutReply` 变体用于单向（发完即忘）的 facility。

### 5. 惰性导入器：`WebSocketLazyImporter`

允许"按需建立 WebSocket 连接"——只有下游真正需要数据时才连接，而不是图启动时就连接。用于大量可选数据源（如几十个可选行情信道）的场景，避免启动时建立大量无用连接。

## 最小可用示例

### 广播发布（供 GUI 订阅）

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:167–171`

```cpp
auto enabledPubSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisher<basic::nlohmann_json_interop::Json<simple_demo::ConfigureResultPOCO>>
    (
        r, "enabledPub"
        , "websocket://0.0.0.0:45678[ignoreTopic=true]"
    );
r.connect(r.actionAsSource(extractEnabled), enabledPubSink);
```

`0.0.0.0` 表示监听所有网卡；`ignoreTopic=true` 让消息不带 topic 头，方便前端直接解析 JSON。

### 广播发布（带协议包装 + 路径）

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:78–83`

```cpp
auto publisherSink2 = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<std::void_t, InputDataPOCO>(
        r, "input data publisher 2"
        , "websocket://localhost:56789:::/data[ignoreTopic=true]"
    );
```

### 服务端 facility 暴露

来源：`tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:288–296`（已简化）

```cpp
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol
    <basic::CBOR,TI::Transaction,TI::TransactionResponse,DI::Update>(
    r
    , transactionLogicCombinationRes.transactionFacility
    , "websocket://127.0.0.1:56789:::transaction"     // identifier 是 URL 路径
    , "transaction_wrapper_3/"
);
```

### 客户端 facility

来源：`tm_examples/db_one_list_subscription/VersionlessSubscriptionClient.cpp:56`（已简化）

```cpp
auto subscriptionFacility = transport::MultiTransportRemoteFacilityManagingUtils<R>
    ::setupSimpleRemoteFacility<GS::Input, GS::Output>(
        "websocket://127.0.0.1:56789:::subscription"
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | WebSocket 长连接推送 | 文件 importer |
| topic | `ignoreTopic=false` 时带 topic 头；`true` 时不带 | 文件格式自带 topic |
| 帧类型 | `binary=true` 用二进制帧 | 不适用 |
| TLS | `wss://` 由 `no_verify` 等控制校验 | 不适用 |
| 前端接入 | 浏览器/GUI 可直连 | 不适用 |

## 易错点

**1. 命名空间是 `web_socket`，不是 `websocket`**

目录名是 `tm_kit/transport/websocket/`，但命名空间是 `dev::cd606::tm::transport::web_socket`。写 `transport::websocket::` 会编译失败。

**2. 路径写在 `identifier`（第 5 段）**

`websocket://localhost:56789:::/data` 中的 `/data` 是第 5 段。写成 `websocket://localhost:56789/data` 会把 `/data` 当作端口解析失败。多个 facility/广播共用一个端口时，靠路径区分。

**3. `ignoreTopic=true` 时收发的信封格式必须两端一致**

`ignoreTopic` 决定消息是否带 topic 头（`src/websocket/WebSocketComponent.cpp:90`）。一端带、一端不带会导致解析错位。前端直连的场景通常两边都设 `ignoreTopic=true`。

**4. `no_verify=true` 会跳过 TLS 证书校验**

`src/websocket/WebSocketComponent.cpp:2148`、`:2243`。仅供自签名证书的测试环境使用，**生产环境绝不能开**——它使中间人攻击成为可能。

**5. `binary` 默认是 `true`，浏览器端需要按二进制处理**

`src/websocket/WebSocketComponent.cpp:108`。前端用 `ws.onmessage` 拿到的会是 `Blob`/`ArrayBuffer` 而非字符串。需要文本帧时显式写 `[binary=false]`。

**6. 两种后端（Boost.Beast / IXWebSocket）行为可能有差异**

`useIXWebSocket` 默认 `false`（`:109`），即默认用 Boost.Beast 实现。IXWebSocket 后端在某些 TLS 或代理场景下行为不同。切换后端前先在同环境验证。

**7. 端口与路径的组合是唯一定位键，但 `ignoreTopic` 不同会被视为不同连接**

与 multicast 类似，底层连接的复用键包含部分属性。同一 `host:port` 上用不同 `ignoreTopic` 建立的两个广播，可能各自开一条连接而不是共享。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| IXWebSocket | `ixwebsocket` | 可选的 WebSocket 后端 | https://github.com/machinezone/IXWebSocket |
| Boost.Beast | `boost` | 默认的 WebSocket 后端 | https://www.boost.org/doc/libs/release/libs/beast/ |
| OpenSSL | 传递依赖 | `wss://` 的 TLS | https://www.openssl.org/ |

`tm_transport/meson.build:17` 声明 `ixwebsocket_dep = dependency('ixwebsocket')`。

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口
- [远程设施](../02-facilities.md) — facility 客户端设置
- [各传输能力矩阵](../00-overview.md)
- [安全与身份校验](../06-security.md) — WebSocket 服务端的 identity checker 用法
- [json_rest 传输](json_rest.md) — 同为 HTTP 生态，适合前端接入
