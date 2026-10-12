---
title: 安全与身份校验
library: tm_transport
headers: [tm_kit/transport/ByteDataHook.hpp, tm_kit/transport/AbstractIdentityCheckerComponent.hpp, tm_kit/transport/EmptyIdentityCheckerComponent.hpp, tm_kit/transport/SimpleIdentityCheckerComponent.hpp, tm_kit/transport/security/SignatureBasedIdentityCheckerComponent.hpp, tm_kit/transport/security/SignatureAndVerifyHookFactoryComponents.hpp, tm_kit/transport/security/SignatureHelper.hpp, tm_kit/transport/TLSConfigurationComponent.hpp, tm_kit/transport/AbstractHookFactoryComponent.hpp]
keywords: [ByteDataHook, UserToWireHook, WireToUserHook, ByteDataHookPair, composeByteDataHookPair, ClientSideSimpleIdentityAttacherComponent, ServerSideSimpleIdentityCheckerComponent, ClientSideSignatureBasedIdentityAttacherComponent, SignatureBasedIdentityCheckerComponent, SignatureHookFactoryComponent, VerifyHookFactoryComponent, SignatureHelper, TLSClientConfigurationComponent, TLSServerConfigurationComponent, TLSClientInfo, TLSServerInfo, 签名, libsodium, 身份校验, 加密, TLS, mTLS]
---

# 安全与身份校验

## 用途

`tm_transport` 的传输层本身**不做任何认证**——任何能连到端口的进程都能发数据。安全能力由两个正交的机制提供：

1. **Hook（字节流变换）** —— `ByteDataHookPair`。在序列化之后、发送之前对字节流做签名、验签、加密、解密。是**端到端**的，与传输无关。
2. **Identity checker（身份校验组件）** —— Environment 组件。在**服务端**校验每个入站请求的身份，在**客户端**把身份附加到出站请求上。是**面向 facility** 的，决定"谁被允许调用"。

两者可以叠加：hook 保证字节流未被篡改，identity 保证调用者有权限。TLS（`TLSConfigurationComponent`）是第三层，保护链路本身。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/ByteDataHook.hpp>
#include <tm_kit/transport/AbstractIdentityCheckerComponent.hpp>
#include <tm_kit/transport/EmptyIdentityCheckerComponent.hpp>
#include <tm_kit/transport/SimpleIdentityCheckerComponent.hpp>
#include <tm_kit/transport/security/SignatureBasedIdentityCheckerComponent.hpp>
#include <tm_kit/transport/security/SignatureAndVerifyHookFactoryComponents.hpp>
#include <tm_kit/transport/security/SignatureHelper.hpp>
#include <tm_kit/transport/TLSConfigurationComponent.hpp>

namespace dev::cd606::tm::transport
```

## 核心类型与签名

### 1. Hook：`ByteDataHook.hpp`

```cpp
struct UserToWireHook {                                          // :10
    std::function<basic::ByteData(basic::ByteData &&)> hook;
};
struct WireToUserHook {                                          // :13
    std::function<std::optional<basic::ByteData>(basic::ByteDataView const &)> hook;
};
struct ByteDataHookPair {                                        // :16
    std::optional<UserToWireHook> userToWire;
    std::optional<WireToUserHook> wireToUser;
};
```

**语义差别很重要**：
- `UserToWireHook`（出方向）返回 `ByteData`，**不能失败**——加密/签名总能成功
- `WireToUserHook`（入方向）返回 `std::optional<ByteData>`，**可以失败**——验签失败时返回 `nullopt`，消息被静默丢弃

组合函数（`:22` 起）：

```cpp
inline UserToWireHook composeUserToWireHook(UserToWireHook h1, UserToWireHook h2);       // :21
inline WireToUserHook composeWireToUserHook(WireToUserHook h1, WireToUserHook h2);       // :26
inline std::optional<UserToWireHook> composeUserToWireHook(
    std::optional<UserToWireHook> h1, std::optional<UserToWireHook> h2);                 // :40
inline std::optional<WireToUserHook> composeWireToUserHook(
    std::optional<WireToUserHook> h1, std::optional<WireToUserHook> h2);                 // :50

// :66 — 注意出入方向顺序相反
inline ByteDataHookPair composeByteDataHookPair(ByteDataHookPair h1, ByteDataHookPair h2);
```

`composeByteDataHookPair` 的注释（`:64`）明确：**出方向 h1 → h2，入方向 h2 → h1**。这保证了"逆操作按相反顺序执行"（先加密后签名 ⇒ 先验签后解密）。

### 2. 抽象 identity 接口：`AbstractIdentityCheckerComponent.hpp`

```cpp
// :16 — 客户端侧
template <class Identity, class Request>
class ClientSideAbstractIdentityAttacherComponent
    : public virtual ClientSideAbstractIdentityAttacherComponentBase<Request> {
public:
    virtual basic::ByteData attach_identity(basic::ByteData &&d) = 0;                 // :15
    virtual std::optional<basic::ByteData> process_incoming_data(basic::ByteData &&d) = 0;  // :16
};

// :28 — 服务端侧
template <class Identity, class Request>
class ServerSideAbstractIdentityCheckerComponent
    : public virtual ServerSideAbstractIdentityCheckerComponentBase<Request> {
public:
    virtual std::optional<std::tuple<Identity, basic::ByteData>> check_identity(basic::ByteData &&d) = 0;  // :26
    virtual basic::ByteData process_outgoing_data(Identity const &identity, basic::ByteData &&d) = 0;      // :27
};
```

> 注释（`:9`）说明两个 `...Base` 类**只用于模板匹配，不是 RTTI 类**。

#### `DetermineClientSideIdentityForRequest<Env, Request>`（`:37`）

编译期 trait，回答"这个环境 + 这个请求类型下，客户端身份是什么"：

```cpp
using IdentityType = ...;                  // 身份类型
using FullRequestType = std::tuple<IdentityType, Request>;   // 有身份时的完整请求类型
static constexpr bool HasIdentity = ...;
using ComponentType = ClientSideAbstractIdentityAttacherComponent<IdentityType, Request>;
```

三个 `bool` 模板参数（`:36`）分别检测：环境是否直接支持该 `Request` 的 attacher、是否支持**解包后**类型（`UnwrappedType<Request>`，即 `Proto<T>`/`Json<T>` 的内层 `T`）的 attacher、是否支持 `std::any` 的 attacher。这解释了为什么身份校验对协议包装是透明的——给 `Proto<T>` 配的身份会自动应用到内层 `T`。

服务端侧有对应的 `DetermineServerSideIdentityForRequest<Env, Request>`。

### 3. 无认证：`EmptyIdentityCheckerComponent`

空的 identity 组件。用于"不需要认证"的场景。此时 `HasIdentity == false`，请求类型就是裸的 `Key<A>`。

### 4. 明文身份：`SimpleIdentityCheckerComponent.hpp`

**只做身份透传，不做认证**——名字里的 "Simple" 是"简单地把身份附在消息前面"，不是"简单的认证"。

```cpp
// :12
template <class Identity, class Request>
class ClientSideSimpleIdentityAttacherComponent
    : public ClientSideAbstractIdentityAttacherComponent<Identity,Request> {
public:
    ClientSideSimpleIdentityAttacherComponent(Identity const &identity);   // :19

    // :30 — 把 (identity, data) 序列化成 CBOR tuple
    virtual basic::ByteData attach_identity(basic::ByteData &&d) override final;
    // :39 — 原样返回
    virtual std::optional<basic::ByteData> process_incoming_data(basic::ByteData &&d) override final;
};

// :45
template <class Identity, class Request>
class ServerSideSimpleIdentityCheckerComponent
    : public ServerSideAbstractIdentityCheckerComponent<Identity,Request> {
public:
    // :47 — 反序列化出 (identity, data)
    virtual std::optional<std::tuple<Identity, basic::ByteData>> check_identity(basic::ByteData &&d) override final;
    // :56 — 原样返回
    virtual basic::ByteData process_outgoing_data(Identity const &identity, basic::ByteData &&d) override final;
};
```

> ⚠️ **`check_identity` 无条件返回成功**（`:47`）——只要 CBOR 能解出 `(Identity, ByteData)` 就接受。**不做任何权限判断**。任何客户端都能声称自己是任何身份。这是最大的安全陷阱。

客户端身份的赋值方式（`tm_examples/simple_demo/qt_client/chart/tmPart.cpp:118`）：

```cpp
env->transport::ClientSideSimpleIdentityAttacherComponent<std::string,ConfigureCommand>::operator=(
    transport::ClientSideSimpleIdentityAttacherComponent<std::string,ConfigureCommand>(
        "qt_chart_enable_client"
    )
);
```

### 5. 签名身份：`SignatureBasedIdentityCheckerComponent.hpp`

用 **libsodium 签名**做真正的身份认证。

```cpp
// :13
class ClientSideSignatureBasedIdentityAttacherComponent {
    SignatureHelper::Signer signer_;
public:
    ClientSideSignatureBasedIdentityAttacherComponent();
    ClientSideSignatureBasedIdentityAttacherComponent(SignatureHelper::PrivateKey const &privateKey);  // :16

    // :23 — 用私钥签名
    // :47 — 用公钥验签
};
```

服务端持有 `SignatureHelper::PublicKeyMap`（公钥表），验签通过才接受请求。**这是推荐的生产方案**。

### 6. Hook 工厂：`SignatureAndVerifyHookFactoryComponents.hpp`

把签名/验签包装成"可插入任意传输的 hook"：

```cpp
// :11 — 出方向：签名
template <class T>
class SignatureHookFactoryComponent : public AbstractOutgoingHookFactoryComponent<T> {
public:
    SignatureHookFactoryComponent(SignatureHelper::PrivateKey const &signKey);
    virtual std::optional<UserToWireHook> defaultHook() override final;   // :19
};

// :30 — 入方向：验签
template <class T>
class VerifyHookFactoryComponent : public AbstractIncomingHookFactoryComponent<T> {
public:
    VerifyHookFactoryComponent(SignatureHelper::PublicKeyMap const &verifyKeys);
    virtual std::optional<WireToUserHook> defaultHook() override final;   // :38
};

// :57 / :77 — 带名字标签的版本（用 name 选择签名/验签密钥）
template <class T> class SignatureWithNameHookFactoryComponent;
template <class T> class VerifyUsingNameTagHookFactoryComponent;
```

带名字的版本用于"一个进程对多个对端、每个对端用不同密钥"的场景——name tag 让接收方知道该用哪把公钥验签。

**示例中的用法**（`tm_examples/simple_demo/secure_executables/MainLogic.cpp:241`）：

```cpp
auto dhHeartbeatHook = VerifyAndDecHookFactoryComponent<transport::HeartbeatMessage>(
    "testkey", calculate_server_public_key
).defaultHook();
```

注意 `VerifyAndDecHookFactoryComponent` 是"验签 + 解密"的组合（示例中与 Diffie-Hellman 密钥交换配合使用），名字里的 `AndDec` 表明它是复合 hook。

### 7. `SignatureHelper`

`security/SignatureHelper.hpp`（实现 `src/security/SignatureHelper.cpp`）提供：

- `SignatureHelper::PrivateKey` / `PublicKeyMap` —— 密钥类型
- `SignatureHelper::Signer` —— 持私钥，`sign(ByteData&&)`
- `SignatureHelper::Verifier` —— 持公钥表，`verify(ByteDataView)`

基于 **libsodium**。

### 8. TLS：`TLSConfigurationComponent.hpp`

```cpp
// :22 — 客户端配置键
TM_BASIC_CBOR_CAPABLE_STRUCT(TLSClientInfoKey, ((std::string, host))((int, port)));
// :25 — 服务端配置键
TM_BASIC_CBOR_CAPABLE_STRUCT(TLSServerInfoKey, ((int, port)));
// :27 — 客户端配置值
TM_BASIC_CBOR_CAPABLE_STRUCT(TLSClientInfo,
    ((std::string, caCertificateFile))
    ((std::string, clientCertificateFile))
    ((std::string, clientKeyFile)));
// :31 — 服务端配置值
TM_BASIC_CBOR_CAPABLE_STRUCT(TLSServerInfo,
    ((std::string, serverCertificateFile))
    ((std::string, serverKeyFile))
    ((std::vector<std::string>, rootCertificateFiles)));

// :35 / :39 — 组件别名（基于 ConfigurationMapComponent）
using TLSClientConfigurationComponent = basic::ConfigurationMapComponent<
    TLSClientInfoKey, TLSClientInfo, basic::struct_field_info_utils::StructFieldInfoBasedHash<TLSClientInfoKey>>;
using TLSServerConfigurationComponent = basic::ConfigurationMapComponent<TLSServerInfoKey, TLSServerInfo, ...>;

// :42 — 两者打包
using TLSConfigurationComponent = infra::Environment<
    TLSClientConfigurationComponent, TLSServerConfigurationComponent>;
```

配置辅助函数（`:45`）：

```cpp
namespace tls {
    template <class Env, typename = std::enable_if_t<std::is_convertible_v<Env *, TLSClientConfigurationComponent *>>>
    void setClientTLSConfigurationItem(
        Env *env, std::string const &host, int port
        , std::string const &caCertFile
        , std::string const &clientCertFile
        , std::string const &clientKeyFile
    );   // 内部调用 env->setConfigurationItem(TLSClientInfoKey{host,port}, TLSClientInfo{...})
}
```

**TLS 配置是按 `(host, port)` 索引的** —— 同一个进程连不同的对端可以用不同的证书。

## 最小可用示例

### 签名心跳的验签（hook 方式）

来源：`tm_examples/simple_demo/secure_executables/MainLogic.cpp:241–254`（已简化）

```cpp
// 1) 构造验签 + 解密的 hook 工厂，需要 "testkey" 标签与对端公钥
auto dhHeartbeatHook = VerifyAndDecHookFactoryComponent<transport::HeartbeatMessage>(
    "testkey", calculate_server_public_key
).defaultHook();

// 2) 把 hook 传给监听器——每条心跳都先验签解密再交给业务
auto dhHeartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r
        , "dh_heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.secure_executables.calculator.heartbeat"
        , dhHeartbeatHook                  // ← WireToUserHook
    );
```

### 客户端身份（Simple identity）

来源：`tm_examples/simple_demo/qt_client/chart/tmPart.cpp:118–122`（已简化）

```cpp
env->transport::ClientSideSimpleIdentityAttacherComponent<std::string,ConfigureCommand>::operator=(
    transport::ClientSideSimpleIdentityAttacherComponent<std::string,ConfigureCommand>(
        "qt_chart_enable_client"           // 客户端声称的身份
    )
);
```

### TLS 配置

```cpp
// 来源：tm_kit/transport/TLSConfigurationComponent.hpp:45 的 tls:: 辅助函数（示例代码库中暂无用例）
using TheEnvironment = infra::Environment<
    /* ... */,
    transport::TLSConfigurationComponent,
    /* ... */
>;
TheEnvironment env;
transport::tls::setClientTLSConfigurationItem(
    &env
    , "broker.example.com", 5671
    , "/etc/ssl/ca.pem"           // CA 证书
    , "/etc/ssl/client.pem"       // 客户端证书（mTLS）
    , "/etc/ssl/client.key"       // 客户端私钥
);
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| Hook | ✓ 完整可用 | 无网络，通常不需要；若回测读的是签名后的历史数据，仍需验签 hook |
| Identity | ✓ 服务端校验入站请求 | 无远端概念；客户端侧类型仍会变成 `tuple<Identity, Request>`（编译期决定） |
| TLS | ✓ | 不适用 |
| 密钥管理 | 需要私钥文件/HSM 与公钥分发 | 不适用 |

**注意 identity 是编译期的**：一旦环境里有 identity checker 组件，facility 的请求类型就变成 `tuple<Identity, A>`（`AbstractIdentityCheckerComponent.hpp:52` 的 `FullRequestType`）。**实时与回测必须使用相同类型的环境**，否则业务代码在两种模式下类型不一致。

## 易错点

**1. `SimpleIdentityCheckerComponent` 不做任何认证**

`ServerSideSimpleIdentityCheckerComponent::check_identity` 只要 CBOR 能解出 `(Identity, ByteData)` 就返回成功（`SimpleIdentityCheckerComponent.hpp:47`）。**客户端可以声称任意身份**。它适合内网可信环境下的"身份标注"，绝不可当作权限控制。需要真正的认证请用 `SignatureBasedIdentityCheckerComponent`。

**2. hook 的入方向失败是静默的**

`WireToUserHook` 返回 `std::optional`（`ByteDataHook.hpp:13`），验签失败时返回 `nullopt`，**消息被直接丢弃，没有任何日志或异常**。排查"心跳/数据莫名收不到"时，先确认 hook 配置是否匹配（密钥、name tag）。

**3. `composeByteDataHookPair` 的出入顺序是相反的**

注释明确（`ByteDataHook.hpp:62`）：出方向 h1 → h2，入方向 h2 → h1。自己组合 hook 时若手写 `composeWireToUserHook(h1, h2)` 而期望与 `composeByteDataHookPair` 一致，顺序会反。**优先用 `composeByteDataHookPair`**。

**4. 有 identity 时请求类型会变，不是运行时行为**

`DetermineClientSideIdentityForRequest` 的 `FullRequestType` 是 `std::tuple<IdentityType, Request>`（`AbstractIdentityCheckerComponent.hpp:52`）。这是**编译期**的：环境里加了 identity 组件之后，facility 的类型签名全部改变。不要试图"运行时开关身份"——需要用不同类型的环境。

**5. 身份类型必须与 `Request` 配对注册**

`ClientSideAbstractIdentityAttacherComponent<Identity, Request>` 是按 `(Identity, Request)` 组合注册的。给 `ConfigureCommand` 注册了 attacher 并不意味着 `QueryCommand` 也有——后者会落回 `HasIdentity == false`。每个请求类型都要单独赋值。

**6. `identity` 检查对协议包装透明，但只对 `UnwrappedType` 透明一层**

trait 的 `Check2` 分支（`:58`）用 `WrapFacilitioidConnectorForSerializationHelpers::UnwrappedType<Request>` 匹配。也就是说 `Proto<T>` 会匹配到为 `T` 注册的 attacher。但**嵌套两层包装（如 `Proto<Json<T>>`）不会继续解包**。

**7. TLS 配置按 `(host, port)` 索引**

`TLSClientInfoKey` 是 `(host, port)`（`TLSConfigurationComponent.hpp:16`）。同一个 host 的不同端口需要分别配置。写错端口会表现为"连接使用了错误的证书"，而不是配置缺失的错误。

**8. 大多数传输也有自己的 TLS 属性，两套机制会并存**

例如 [Redis 传输](03-transports/redis.md) 的 `ca_cert`/`client_cert`/`client_key` 属性、[WebSocket](03-transports/websocket.md) 的 `no_verify`、[json_rest](03-transports/json_rest.md) 的 `no_verify`。`TLSConfigurationComponent` 是框架层的统一配置入口，但各传输实现是否真正读取它需要按实现确认。**配置 TLS 时两条路径都要检查**。

**9. `no_verify=true` 在任何传输上都不能用于生产**

`src/websocket/WebSocketComponent.cpp:2148`、`src/json_rest/JsonRESTComponent.cpp:1689`。它关闭证书校验，使中间人攻击成为可能。仅供自签名证书的本地测试。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| libsodium | `libsodium` | 签名、验签、加密原语 | https://doc.libsodium.org/ |
| OpenSSL | 传递依赖（各传输） | TLS | https://www.openssl.org/ |
| Boost | `boost` | `boost::asio::ssl` | https://www.boost.org/doc/libs/release/doc/html/boost_asio.html |
| certify | 随仓库 `external/certify/` | TLS 证书处理 | https://github.com/djarek/certify |

`tm_transport/meson.build:14` 声明 `libsodium_dep = dependency('libsodium')`。`src/BoostCertifyAdaptor.cpp`（`src/meson.build` 的源文件清单末位）是 Boost 与 certify 的适配层。

仓库根 `CLAUDE.md` 记录的相关 `.pc` 修补：无（libsodium 相关坑未记录）。

## 相关章节

- [广播](01-broadcast.md) — `hook` / `hookFactory` 参数的使用位置
- [远程设施](02-facilities.md) — `ByteDataHookPair hooks` 参数、`DetermineClientSideIdentityForRequest`
- [各传输详解](03-transports/) — 各传输自身的 TLS 属性
- [心跳与告警](05-heartbeat-and-alert.md) — 心跳的签名验签是常见用法
- [序列化格式](../tm_basic/03-serialization.md) — `ByteData`、`ByteDataView`、协议包装器
