---
title: GrpcInterop 传输
library: tm_transport
headers: [tm_kit/transport/grpc_interop/GrpcInteropComponent.hpp, tm_kit/transport/grpc_interop/GrpcClientFacility.hpp, tm_kit/transport/grpc_interop/GrpcServerFacility.hpp, tm_kit/transport/grpc_interop/GrpcServiceInfo.hpp, tm_kit/transport/grpc_interop/GrpcConnectionLocatorUtils.hpp]
keywords: [grpc_interop, GrpcInteropComponent, GrpcClientFacilityFactory, GrpcServerFacilityWrapper, GrpcServiceInfo, GrpcSerializationHelper, protobuf, proto, 跨语言, RPC, 双向流, single_rpc, namespace/service/method]
---

# GrpcInterop 传输

## 用途

与 **gRPC** 服务互操作。**只支持 on-order facility，不支持广播**。

它的核心价值是**跨语言、跨团队**：TM Kit 进程与 Java / Go / Python / C# 服务互通时，gRPC + protobuf 是通用契约。`tm_examples/db_subscription/` 与 `db_one_list_subscription/` 都用它把 transaction facility 暴露给外部客户端。

两个方向：

- **服务端**：把 TM Kit 的 facility 暴露成 gRPC 服务，供外部（含 `TMTransportDotNet` / `python_lib` / `node_lib` 绑定，见下文说明）调用。
- **客户端**：调用外部 gRPC 服务。

**要求请求/响应类型是 protobuf 风格可序列化的**——`GrpcClientFacilityFactory` 与 `GrpcServerFacilityWrapper` 都对 `Req`/`Resp` 有 `ProtobufStyleSerializableChecker<...>::IsProtobufStyleSerializable()` 的 `enable_if` 约束（`GrpcClientFacility.hpp:42`、`GrpcServerFacility.hpp:33`）。普通 CBOR 结构体不满足，需要加 `TM_BASIC_CBOR_CAPABLE_STRUCT_PROTOCOL_SERIALIZE` 之类生成 protobuf 表示。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/grpc_interop/GrpcInteropComponent.hpp>
#include <tm_kit/transport/grpc_interop/GrpcClientFacility.hpp>
#include <tm_kit/transport/grpc_interop/GrpcServerFacility.hpp>
#include <tm_kit/transport/grpc_interop/GrpcServiceInfo.hpp>

namespace dev::cd606::tm::transport::grpc_interop
```

## 核心类型与签名

### 1. `GrpcInteropComponent`（`GrpcInteropComponent.hpp:21`）

```cpp
class GrpcInteropComponent {
public:
    GrpcInteropComponent();
    virtual ~GrpcInteropComponent();

    std::shared_ptr<grpc::Channel> grpc_interop_getChannel(ConnectionLocator const &locator);   // :31
    void grpc_interop_registerService(ConnectionLocator const &locator, grpc::Service *);       // :32

    // :36 — 注释明确说明：这组 API 不是建立 gRPC 客户端的首选方式，
    //       仅为兼容 MultiTransportRemoteFacility 而保留
    std::function<void(basic::ByteDataWithID &&)> grpc_interop_setRPCClient(
        ConnectionLocator const &locator
        , std::function<void(bool, std::string const &, std::optional<std::string> &&)> client
        , std::optional<ByteDataHookPair> hookPair = std::nullopt
    );
    void grpc_interop_removeRPCClient(ConnectionLocator const &locator);
    void finalizeEnvironment();
};
```

### 2. Locator 语法

```
grpc_interop://host:port:::namespaceName/serviceName/methodName[single_rpc=false]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` / `port` | gRPC 服务地址 | —— |
| `identifier` | **`namespace/service/method` 三段式路径** | —— |
| `single_rpc` | 单次 RPC（unary）还是流式 | `false`（`src/grpc_interop/GrpcConnectionLocatorUtils.cpp:26`） |

`identifier` 的解析在 `src/grpc_interop/GrpcConnectionLocatorUtils.cpp:12` 的 `parseServiceInfo`：

- 用 `/` 分割，**前导空段被跳过**（因此 `grpc_interop://host:port:::db_subscription/Main/Transaction` 中 `/db_subscription/Main/Transaction` 的前导 `/` 不会产生空段）
- 不足 3 段时抛 `GrpcInteropComponentException("Wrong connection locator identity: must be namespace/service/method")`

解析结果结构体（`GrpcServiceInfo.hpp:17`）：

```cpp
TM_BASIC_CBOR_CAPABLE_STRUCT(GrpcServiceInfo,
    ((std::string, namespaceName))
    ((std::string, serviceName))
    ((std::string, methodName))
    ((bool, isSingleRpcCall))
);
```

`grpcServiceInfoAsEndPointString`（`:23`）把它还原成 gRPC 的端点串 `/<namespace>.<service>/<method>`。

### 3. 客户端工厂：`GrpcClientFacilityFactory<M>`（`GrpcClientFacility.hpp:37`）

```cpp
template <class M, typename = std::enable_if_t<
    infra::app_classification_v<M> == infra::AppClassification::RealTime
    && std::is_convertible_v<typename M::EnvironmentType *, GrpcInteropComponent *>
>>
class GrpcClientFacilityFactory {
public:
    template <class Req, class Resp>
    static auto createClientFacility(ConnectionLocator const &locator)
        -> std::shared_ptr<typename M::template OnOrderFacility<Req, Resp>>;
};
```

内部实现是 `M::IExternalComponent` + `AbstractOnOrderFacility<Req,Resp>` + 带线程的 `ThreadedHandler`（`:52`），因此拥有自己的后台线程，通过 `grpc::Channel` 与服务端通信。

### 4. 服务端包装：`GrpcServerFacilityWrapper<M>`（`GrpcServerFacility.hpp:29`）

```cpp
template <class M, typename = std::enable_if_t<
    infra::app_classification_v<M> == infra::AppClassification::RealTime
    && std::is_convertible_v<typename M::EnvironmentType *, GrpcInteropComponent *>
>>
class GrpcServerFacilityWrapper {
private:
    static void wrapFacilitioidConnector_internal(
        R &r
        , std::optional<std::string> const &registeredNameForFacility
        , typename infra::AppRunner<M>::template FacilitioidConnector<Req,Resp> const &toBeWrapped
        , ConnectionLocator const &locator
        , std::string const &wrapperItemsNamePrefix
    );
};
```

内部用 `grpc::ServerWriteReactor<Resp>` 支持流式响应（`GrpcServerFacility.hpp:59`），服务端可以把一次请求的多个响应分多次推回。

**实务上一般不直接用它**，而是通过 `MultiTransportFacilityWrapper::wrapWithProtocol` 统一入口（内部会分发到 grpc 实现）。

## 最小可用示例

### 服务端：把一个 facility 同时暴露到 gRPC、WebSocket、RabbitMQ、组播

来源：`tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:280–301`（已简化）

```cpp
// 同一个 transaction facility，四种暴露方式
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol
    <basic::proto_interop::Proto,TI::Transaction,TI::TransactionResponse,DI::Update>(
    r
    , transactionLogicCombinationRes.transactionFacility
    , "grpc_interop://127.0.0.1:12345:::db_one_list_subscription/Main/Transaction"
    , "transaction_wrapper_2/"
);
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol
    <basic::CBOR,TI::Transaction,TI::TransactionResponse,DI::Update>(
    r
    , transactionLogicCombinationRes.transactionFacility
    , "websocket://127.0.0.1:56789:::transaction"
    , "transaction_wrapper_3/"
);
```

注意 gRPC 那一路用了 `basic::proto_interop::Proto` 包装（gRPC 要求 protobuf），WebSocket 那一路用 `basic::CBOR`。

### 客户端：连接本地事务服务

来源：`tm_examples/db_subscription/DBSubscriptionServer.cpp:289`、`ReadOnlyDBServer.cpp:103`（信道字符串）

```cpp
// 服务端注册
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol
    <basic::proto_interop::Proto,TI::Transaction,TI::TransactionResponse,DI::Update>(
    r
    , transactionLogicCombinationRes.transactionFacility
    , "grpc_interop://127.0.0.1:12345:::db_subscription/Main/Transaction"
    , "transaction_wrapper_2/"
);

// 只读查询走另一个 service/method
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol
    <basic::proto_interop::Proto,QueryInput,QueryOutput>(
    r
    , readonlyFacility
    , "grpc_interop://127.0.0.1:12345:::db_subscription/Readonly/Query"
    , "readonly_wrapper/"
);
```

一个 gRPC 端口（12345）上通过 `namespace/service/method` 区分多个 facility——`db_subscription/Main/Transaction` 与 `db_subscription/Readonly/Query` 共用 `db_subscription` 命名空间但属于不同 service。

## 与语言绑定的关系

`tm_transport` 仓库根下有 `TMTransportDotNet/`、`python_lib/`、`node_lib/`，是 TM Kit 的 C#/Python/TypeScript 绑定。这些绑定通过 gRPC 与 C++ 侧通信，因此 **`grpc_interop` 是跨语言集成的唯一通道**。绑定本身的完整参考不在本套文档范围内。

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | gRPC 调用 | 应替换为本地 mock facility |
| 序列化 | 必须是 protobuf 风格可序列化 | 不适用 |
| 流式响应 | `ServerWriteReactor` 支持多次回调 | 不适用 |
| 外部客户端 | 任何语言的 gRPC 客户端 | 不适用 |

## 易错点

**1. 请求/响应类型必须是 protobuf 风格可序列化的**

`ProtobufStyleSerializableChecker<Req>::IsProtobufStyleSerializable()` 是 `enable_if` 条件（`GrpcClientFacility.hpp:42`、`GrpcServerFacility.hpp:33`）。只加了 `TM_BASIC_CBOR_CAPABLE_STRUCT` 的结构体不满足。不满足时的报错是"找不到匹配的重载"，而不是清晰的提示——排查时先确认类型的序列化宏。

**2. `identifier` 必须恰好三段（namespace/service/method）**

不足 3 段抛 `GrpcInteropComponentException`（`src/grpc_interop/GrpcConnectionLocatorUtils.cpp:20`）。多于 3 段的**不会报错**——`parseServiceInfo` 只取前 3 段（`:24` 的 `parts[ii]`、`parts[ii+1]`、`parts[ii+2]`），多余的被忽略。写错路径段数时可能静默连到错误的 method。

**3. 只有 facility，没有广播**

`MultiTransportBroadcastListenerConnectionType` 中没有 grpc_interop（`tm_kit/transport/MultiTransportBroadcastListener.hpp:89`）。需要服务端推送用 [websocket](websocket.md)。

**4. gRPC 要求客户端和服务端的 proto 定义完全一致**

包括字段编号、类型、package 名。TM Kit 侧通过 `basic::proto_interop::Proto` 包装把 C++ 结构体映射到 protobuf，生成的字段布局必须与外部服务一致。字段顺序变化会导致静默的数据错位。

**5. `single_rpc` 决定 unary 还是流式，两端必须一致**

`single_rpc` 默认 `false`（`src/grpc_interop/GrpcConnectionLocatorUtils.cpp:26`），即默认流式。如果客户端按 unary 调用而服务端按流式实现（或反之），gRPC 会返回 `UNIMPLEMENTED`。

**6. `MultiTransportFacilityWrapper::wrapWithProtocol<Proto, ...>` 是推荐入口，不要直接用 `GrpcServerFacilityWrapper`**

后者是内部实现类（`wrapFacilitioidConnector_internal` 是 `private`）。通过 `MultiTransportFacilityWrapper` 的统一入口可以同时挂多路传输，且自动处理心跳注册。

**7. gRPC 的依赖体积很大**

gRPC + Abseil + protobuf 会显著增大二进制与编译时间。仓库根 `CLAUDE.md` 提到 debug 构建的日志可达 ~1 GB，主因就是 gRPC/Abseil 的模板与弃用警告。只做进程内通信的项目应只链接需要的传输组件，不要用 `AllNetworkTransportComponents`。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| gRPC（C++） | `grpc` | 传输实现 | https://grpc.io/docs/languages/cpp/ |
| Protocol Buffers | 由 gRPC 传递依赖 | 序列化 | https://protobuf.dev/ |
| Abseil | 由 gRPC 传递依赖 | gRPC 的基础库 | https://abseil.io/ |
| OpenSSL | 传递依赖 | TLS 与凭据 | https://www.openssl.org/ |

`tm_transport/meson.build:11` 声明 `grpc_dep = dependency('grpc')`。

> ⚠️ **本环境的 `.pc` 修补**：`grpc.pc` 被补上了 `-lgrpc++`（Libs）与 `grpc++`（Requires），因为 `tm_transport` 使用的是 gRPC 的 **C++ API**，而原 `.pc` 只声明了 C 库。缺少这一项会产生大量 gRPC C++ 符号的未定义引用。详见仓库根 `CLAUDE.md` 的 "Known Build Issues & Fixes" 第 2 条。

对 `.pc` 文件的任何修改都需要**完整重配置**（meson 在 configure 阶段缓存依赖信息），即 `build.sh` 里选 "clean rebuild"。

## 相关章节

- [远程设施](../02-facilities.md) — `MultiTransportFacilityWrapper::wrapWithProtocol` 统一入口
- [transaction v2](../../tm_basic/09-transaction.md) — 示例中被暴露的 transaction facility 来自 `transactionLogicCombination`
- [序列化格式](../../tm_basic/03-serialization.md) — `proto_interop::Proto` 包装器
- [各传输能力矩阵](../00-overview.md)
- [构建与 vcpkg `.pc` 修补](../../BUILD.md) — grpc.pc 的具体改动
