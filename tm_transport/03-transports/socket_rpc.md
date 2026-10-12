---
title: SocketRPC 传输
library: tm_transport
headers: [tm_kit/transport/socket_rpc/SocketRPCComponent.hpp, tm_kit/transport/socket_rpc/SocketRPCOnOrderFacility.hpp]
keywords: [socket_rpc, SocketRPCComponent, SocketRPCOnOrderFacility, 裸 TCP, 请求响应, RPC, Boost.Asio, ByteDataWithID, 单向, 双向, 无 broker]
---

# SocketRPC 传输

## 用途

基于 **裸 TCP** 的 on-order facility 传输。没有 broker、没有 HTTP/gRPC 的协议开销，就是客户端连上服务端、发请求、收响应。

适合：进程间的高频请求-响应（如策略进程 → 风控前置的实时校验）、对延迟敏感的 RPC。不适合：需要一对多订阅（用广播传输）、需要跨语言互操作（用 `grpc_interop` 或 `json_rest`）。

**注意：SocketRPC 只支持 facility，不支持广播**——`MultiTransportBroadcastListenerConnectionType`（`tm_kit/transport/MultiTransportBroadcastListener.hpp:89`）中没有它。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/socket_rpc/SocketRPCComponent.hpp>
#include <tm_kit/transport/socket_rpc/SocketRPCOnOrderFacility.hpp>

namespace dev::cd606::tm::transport::socket_rpc
```

## 核心类型与签名

### 1. `SocketRPCComponent`（`SocketRPCComponent.hpp`）

Environment 组件。提供 `socket_rpc_threadHandles()` 用于诊断。

### 2. Locator 语法

```
socket_rpc://host:port
```

| 字段 | 含义 |
|---|---|
| `host` | 服务端地址。**服务端固定绑定 `0.0.0.0`**（`src/socket_rpc/SocketRPCComponent.cpp:426`），此字段只对客户端有意义 |
| `port` | 端口（必填） |
| `identifier` | 未使用 |
| 属性块 | 未使用 |

### 3. 底层工厂：`SocketRPCOnOrderFacility<Env>`（`SocketRPCOnOrderFacility.hpp:21`）

```cpp
template <class Env>
class SocketRPCOnOrderFacility {
public:
    // :37 — 双向版本：每条消息带一个 ID，响应按 ID 配对
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithID>>
    createOnOrderFacilityRPCConnectorIncomingLegOnly(
        ConnectionLocator const &locator
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    );

    // :186 / :599 / :1019 — 带类型的 RPC facility
    template <class A, class B>
    static std::shared_ptr<typename M::template OnOrderFacility<A, B>>
    createTypedRPCOnOrderFacility(
        ConnectionLocator const &locator
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    );
};
```

内部实现是 `RealTimeAppComponents<Env>::IExternalComponent` + `AbstractOnOrderFacility<A,B>` + `IControllableNode<Env>`（`:189`）——因此它作为外部组件拥有自己的线程，并且可以通过 `AppRunner::controlAll` 控制。

### 4. 单向模式

`SocketRPCOnOrderFacility` 另有单向（one-way）变体，用于只发不收的场景（对应 `MultiTransportRemoteFacility` 的 silent handler 用法）。具体重载见 `SocketRPCOnOrderFacility.hpp:599` 与 `:1019` 附近的实现。

## 最小可用示例

`tm_examples/` 中暂无 socket_rpc 的直接用例。按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/socket_rpc/SocketRPCOnOrderFacility.hpp:186 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::socket_rpc::SocketRPCComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;
using R = infra::AppRunner<M>;
```

### 服务端：把 facility 暴露到 TCP 端口

```cpp
// 来源：tm_examples 中通用 facility 服务端模式（已简化）
auto facility = M::fromAbstractOnOrderFacility(new RiskCheckFacility());
r.registerOnOrderFacility("risk_check", facility);

transport::MultiTransportFacilityWrapper<R>::wrap<RiskCheckRequest, RiskCheckResult>(
    r, facility, "socket_rpc://0.0.0.0:12347", "risk_wrapper/"
);
```

### 客户端：连接该端口

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:104 的模式（已简化）
auto riskCheck = transport::MultiTransportRemoteFacilityManagingUtils<R>
    ::setupSimpleRemoteFacility<RiskCheckRequest, RiskCheckResult>(
        r
        , "socket_rpc://127.0.0.1:12347"
    );
```

注意 `setupSimpleRemoteFacility` 是**静态函数**（不需要 `R` 参数即可调用，`tm_kit/transport/MultiTransportRemoteFacilityManagingUtils.hpp:1494`），返回 `OnOrderFacilityPtr`；上面的调用用了带 `r` 的 `:1512` 重载。

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 调用时序 | 异步，需处理网络超时与重连 | 同步本地调用 |
| 服务端绑定 | 固定 `0.0.0.0:port` | 不适用 |
| 传输可靠 | TCP，可靠有序 | 不适用 |
| 消息边界 | 由框架的消息帧界定 | 不适用 |

## 易错点

**1. 服务端忽略 locator 的 `host`，固定绑定 `0.0.0.0`**

`src/socket_rpc/SocketRPCComponent.cpp:426` 用 `resolver.resolve("0.0.0.0", port)`。写 `socket_rpc://127.0.0.1:12347` 作为服务端**不会**限制为只监听回环——它仍然监听所有网卡。要限制访问来源必须靠 identity checker 或防火墙。

**2. 只有 facility，没有广播**

`MultiTransportBroadcastListenerConnectionType` 中没有 socket_rpc（`tm_kit/transport/MultiTransportBroadcastListener.hpp:89`）。把 `socket_rpc://...` 传给 `oneBroadcastListener` 会抛 `std::runtime_error`。

**3. 需要在图启动前确保服务端先监听**

TCP 连接失败时的重试行为由组件决定。客户端早于服务端启动会连接失败。启动顺序敏感的场景请用带心跳服务发现的 `setupOneNonDistinguishedRemoteFacility`。

**4. 无 broker，没有消息持久化与补发**

服务端重启期间客户端发出的请求会失败。需要"至少一次"语义要自己在业务层加重试与幂等。

**5. 端口暴露在网络上是无认证的**

裸 TCP + 框架序列化，任何能连到该端口的进程都能发请求。生产环境必须叠加 identity checker / 签名 hook（见 [安全与身份校验](../06-security.md)）。

**6. 客户端使用 `MultiTransportRemoteFacilityManagingUtils::setupSimpleRemoteFacility`，不要直接调底层工厂**

底层的 `SocketRPCOnOrderFacility::createTypedRPCOnOrderFacility` 返回的是 `OnOrderFacility`，需要自己注册到 runner 并处理心跳/服务发现。`setupSimpleRemoteFacility` 已经封装好这些步骤。

## 第三方依赖

基于 **Boost.Asio** 的 TCP socket 实现，无额外第三方库（`tm_transport/meson.build` 的 `boost_dep`）。

Boost.Asio 官方文档：https://www.boost.org/doc/libs/release/doc/html/boost_asio.html

## 相关章节

- [远程设施](../02-facilities.md) — `setupSimpleRemoteFacility`、`setupOneNonDistinguishedRemoteFacility`
- [grpc_interop 传输](grpc_interop.md) — 需要跨语言或 schema 时替代
- [json_rest 传输](json_rest.md) — HTTP/JSON 版本
- [各传输能力矩阵](../00-overview.md)
