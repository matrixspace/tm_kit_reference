---
title: Redis 传输
library: tm_transport
headers: [tm_kit/transport/redis/RedisComponent.hpp, tm_kit/transport/redis/RedisImporterExporter.hpp, tm_kit/transport/redis/RedisOnOrderFacility.hpp]
keywords: [Redis, RedisComponent, RedisImporterExporter, RedisOnOrderFacility, pub sub, hiredis, redis_ssl, ca_cert, client_cert, client_key, glob 通配, RPC, 键值存储]
---

# Redis 传输

## 用途

基于 Redis 的 pub/sub 与请求-响应传输。**同时支持广播与 on-order facility**，且支持 TLS 双向认证。

选它通常是因为基础设施里已经有 Redis（缓存、队列），不想为消息通信再引入 RabbitMQ。相比 RabbitMQ：

- 更轻量，延迟略低
- **没有持久化语义**（Redis pub/sub 是 fire-and-forget；订阅者掉线即丢消息）
- topic 通配用 Redis glob（`*`、`?`、`[...]`），与 AMQP 语义不同

Redis 传输与 [Redis 共享链](../04-shared-chains.md)、[named_value_store](../07-kv-store-components.md) 共用同一个 `RedisComponent`。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/redis/RedisComponent.hpp>
#include <tm_kit/transport/redis/RedisImporterExporter.hpp>
#include <tm_kit/transport/redis/RedisOnOrderFacility.hpp>

namespace dev::cd606::tm::transport::redis
```

## 核心类型与签名

### 1. `RedisComponent`（`RedisComponent.hpp:27`）

Environment 组件。提供 `redis_threadHandles()` 用于诊断。异常类型 `RedisComponentException`（`:22`）。

### 2. Locator 语法

```
redis://host:port:::identifier[ca_cert=...][client_cert=...][client_key=...]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` | Redis 服务地址 | —— |
| `port` | 端口；**为 0 时用 6379**（`src/redis/RedisComponent.cpp:142`） | 0 → 6379 |
| `userName` / `password` | Redis 6+ ACL 凭据 / 传统密码 | —— |
| `identifier` | facility 模式下的 **RPC topic**（`:964`、`:1136`） | —— |
| `ca_cert` | 服务端 CA 证书路径（TLS） | `""`（`:122`） |
| `client_cert` | 客户端证书路径（TLS 双向认证） | `""`（`:123`） |
| `client_key` | 客户端私钥路径 | `""`（`:124`） |

注意 `redisConnect` 直接用 `host` 与 `port`（`:102`），三个证书属性同时给出才启用 TLS。

### 3. 广播工厂：`RedisImporterExporter<M>`（`RedisImporterExporter.hpp:18`）

```cpp
template <class M>
class RedisImporterExporter {
public:
    // :21 — topic 默认 "*"（订阅全部）
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::string const &topic = "*"
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

    // :66
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(
        ConnectionLocator const &locator
        , std::string const &topic = "*"
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

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

topic 类型是 `std::string`（**不是** variant），用 Redis 的 glob 语法。

### 4. Facility 工厂：`RedisOnOrderFacility<Env>`

```cpp
template <class Env>
class RedisOnOrderFacility {
public:
    template <class A, class B>
    static std::shared_ptr<typename infra::RealTimeApp<Env>::template OnOrderFacility<A,B>>
    createTypedRPCOnOrderFacility(
        ConnectionLocator const &locator
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    );
};
```

facility 模式下 `identifier` 是 RPC topic（`src/redis/RedisComponent.cpp:964`），与广播模式的 topic 是两套命名空间。

## 最小可用示例

### 服务端 facility

来源：`tm_examples/simple_demo/secure_executables/Calculator.cpp:156–173`

```cpp
using R = infra::AppRunner<M>;
R r(&env);

auto facility = M::fromAbstractOnOrderFacility(new CalculatorFacility());
r.registerOnOrderFacility("facility", facility);

// 把本地 facility 暴露成 Redis RPC 服务；identifier 是 RPC topic
transport::MultiTransportFacilityWrapper<R>::wrap<CalculateCommand,CalculateResult>(
    r, facility, "redis://localhost:6379:::test_queue", "wrapper/"
);

// 同一进程可以同时暴露多个 facility 到不同 topic
auto dhFacility = M::template liftPureOnOrderFacility<std::tuple<std::string, DHHelperCommand>>(
    boost::hana::curry<2>(std::mem_fn(&DHServerHelper::process))(dh.get())
);
r.registerOnOrderFacility("dh_server_facility", dhFacility);
transport::MultiTransportFacilityWrapper<R>::wrap<DHHelperCommand,DHHelperReply>(
    r, dhFacility, "redis://localhost:6379:::test_dh_queue", "dh_wrapper/"
);
```

注意 `wrap` 是 **`static void`**，直接操作 `runner`，不像 `facilityWrapper` 那样返回可复用的 wrapper 对象。

> 客户端订阅 Redis 广播的用例在 `tm_examples/` 中暂无——仓库里的示例都走 RabbitMQ 心跳 + ZeroMQ/WebSocket 数据。上面的服务端用例是 Redis 在示例中唯一被直接使用的传输路径。

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | Redis pub/sub 推送 | 文件 importer |
| 消息保留 | **无**——纯 fire-and-forget，订阅者不在线即丢失 | 文件数据完整 |
| topic 通配 | Redis glob（`*`、`?`、`[...]`） | 文件格式自带 topic |
| TLS | `ca_cert`/`client_cert`/`client_key` | 不适用 |

**与 Redis 共享链的对照**：如果需要在回测中重放 Redis 上的数据，不要指望 pub/sub 能补历史——应改用 [Redis 共享链](../04-shared-chains.md)（`RedisChain`），它把数据持久化为 Redis 里的键，支持从头读取。

## 易错点

**1. Redis pub/sub 不保留消息**

订阅者启动之前发布的消息**永久丢失**，Redis 不提供补发。这是与 RabbitMQ `durable` 最本质的差别。需要"新订阅者能拿到当前状态"时，模式是：订阅者启动后用一次 facility 请求拉取快照，再靠 pub/sub 接收增量。

**2. topic 通配符是 Redis glob，不是 AMQP 语法**

Redis：`*`（任意长度）、`?`（单字符）、`[abc]`（字符集）。AMQP：`*`（一个词）、`#`（多个词）。框架在 `MultiTransportBroadcastListenerTopicHelper` 中会把 `#` 转成 `*` 以统一书写（`tm_kit/transport/MultiTransportBroadcastListener.hpp:251` 的 `redisTopicHelper`），但**其他 AMQP 特有语法不会被转换**。

**3. `port` 为 0 时静默回落到 6379**

`locator.port()==0 ? 6379 : locator.port()`（`src/redis/RedisComponent.cpp:142`）。写 `redis://127.0.0.1:::` 会连 6379；但如果你的 Redis 跑在别的端口且忘了写，会静默连错端口而非报错。

**4. TLS 需要三个证书属性同时给出**

`ca_cert`、`client_cert`、`client_key` 分别读取（`:122–124`）。只给 `ca_cert` 不启用双向认证；三者全给才建立完整的 mTLS 连接。缺项时的失败模式是连接被对端拒绝，错误信息来自 hiredis。

**5. `identifier` 在广播与 facility 下含义不同**

facility 时它是 RPC topic（`src/redis/RedisComponent.cpp:964`），广播时 locator 的 `identifier` 不被使用（topic 由函数参数给出）。同一个 locator 同时用于两者时要留意命名冲突。

**6. Redis 单线程模型，大消息会阻塞整个实例**

Redis 是单线程处理命令的。发布大消息（MB 级）会阻塞该 Redis 实例上的**所有**操作，包括其他应用的缓存读写。高吞吐场景请控制单条消息大小。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| hiredis | `hiredis` | Redis C 客户端 | https://github.com/redis/hiredis |
| hiredis_ssl | `hiredis_ssl`（可选） | TLS 支持 | https://github.com/redis/hiredis |
| OpenSSL | 由 hiredis_ssl 传递依赖 | TLS 实现 | https://www.openssl.org/ |

`tm_transport/meson.build:7` 声明 `redis_dep = [dependency('hiredis'), dependency('hiredis_ssl', required: false)]`——注意 `hiredis_ssl` 是 **optional**，缺失时 TLS 相关功能不可用。

仓库根 `CLAUDE.md` 记录的相关 `.pc` 修补：无（redis 相关的坑主要在共享链一侧）。

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口
- [远程设施](../02-facilities.md) — `setupSimpleRemoteFacility` 等
- [共享链后端](../04-shared-chains.md) — `RedisChain`，支持持久化与历史读取
- [键值存储组件](../07-kv-store-components.md) — `named_value_store` 的 Redis/Etcd 后端
- [各传输能力矩阵](../00-overview.md)
