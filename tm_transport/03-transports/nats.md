---
title: NATS 传输
library: tm_transport
headers: [tm_kit/transport/nats/NATSComponent.hpp, tm_kit/transport/nats/NATSImporterExporter.hpp, tm_kit/transport/nats/NATSOnOrderFacility.hpp]
keywords: [NATS, NATSComponent, NATSImporterExporter, NATSOnOrderFacility, libnats, nats.c, ca_cert, client_cert, client_key, 通配, 轻量消息总线, RPC]
---

# NATS 传输

## 用途

基于 NATS 的 pub/sub 与请求-响应传输。**同时支持广播与 on-order facility**，支持 TLS。

NATS 的定位介于 Redis pub/sub 与 RabbitMQ 之间：比 RabbitMQ 轻、启动快、延迟低，但不提供持久化（除非用 JetStream，本传输未使用）。适合服务间的高频消息与 RPC。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/nats/NATSComponent.hpp>
#include <tm_kit/transport/nats/NATSImporterExporter.hpp>
#include <tm_kit/transport/nats/NATSOnOrderFacility.hpp>

namespace dev::cd606::tm::transport::nats
```

## 核心类型与签名

### 1. `NATSComponent`（`NATSComponent.hpp:27`）

Environment 组件。提供 `nats_threadHandles()` 用于诊断。异常类型 `NATSComponentException`（`:22`）。

### 2. Locator 语法

```
nats://host:port:::identifier[ca_cert=...][client_cert=...][client_key=...]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` | NATS 服务地址 | —— |
| `port` | 端口（4222） | —— |
| `userName` / `password` | NATS 凭据 | —— |
| `identifier` | facility 模式下的 subject | —— |
| `ca_cert` | 服务端 CA 证书路径 | `""`（`src/nats/NATSComponent.cpp:20`） |
| `client_cert` | 客户端证书路径 | `""`（`:21`） |
| `client_key` | 客户端私钥路径 | `""`（`:22`） |

### 3. 广播工厂：`NATSImporterExporter<M>`（`NATSImporterExporter.hpp:18`）

```cpp
template <class M>
class NATSImporterExporter {
public:
    // :21 — topic 默认 "*"
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

`topic` 参数类型是 `std::string`。

### 4. Facility 工厂：`NATSOnOrderFacility<Env>`

```cpp
template <class Env>
class NATSOnOrderFacility {
public:
    template <class A, class B>
    static std::shared_ptr<typename infra::RealTimeApp<Env>::template OnOrderFacility<A,B>>
    createTypedRPCOnOrderFacility(
        ConnectionLocator const &locator
        , std::optional<ByteDataHookPair> hooks = std::nullopt
    );
};
```

### 5. topic 通配符的特殊处理

NATS 自己的通配符是 `*`（单级）与 `>`（多级，只能出现在末尾）。框架把 `#` 转成 `*` 以统一书写（`tm_kit/transport/MultiTransportBroadcastListener.hpp:257` 的 `natsTopicHelper`）：

```cpp
static std::string natsTopicHelper(std::string const &input) {
    std::string ret = input;
    std::replace(ret.begin(), ret.end(), '#', '*');
    return ret;
}
```

**注意**：NATS 的多级通配 `>` **不会被框架自动转换**，写在 topic 里会原样传给 NATS（正确行为）。但把 AMQP 的 `foo.#.bar` 拿去 NATS 用时，`#` 会变成 `*`（单级），语义与 AMQP 的"多级"不同。

## 最小可用示例

`tm_examples/` 中暂无 NATS 的直接用例。按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/nats/NATSImporterExporter.hpp:21 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::nats::NATSComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;

// 订阅：subject 通配
auto subscriber = transport::nats::NATSImporterExporter<M>
    ::template createTypedImporter<TickData>(
        transport::ConnectionLocator::parse("127.0.0.1:4222"),
        std::string("market.*"),
        std::nullopt
    );

// 服务端 facility
transport::MultiTransportFacilityWrapper<R>::wrap<Query, Reply>(
    r, queryFacility, "nats://127.0.0.1:4222:::query.subject", "query_wrapper/"
);
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | NATS 推送 | 文件 importer |
| 消息保留 | 默认无（非 JetStream）；订阅者不在线即丢 | 文件数据完整 |
| topic 通配 | NATS 语法：`*` 单级、`>` 多级（仅末尾） | 文件格式自带 topic |
| TLS | `ca_cert`/`client_cert`/`client_key` | 不适用 |

## 易错点

**1. `#` 会被转成 `*`，但两者语义并不等价**

框架对 NATS 做 `#` → `*` 替换（`tm_kit/transport/MultiTransportBroadcastListener.hpp:257`）。AMQP 的 `#` 是"零个或多个词"，NATS 的 `*` 是"恰好一个词"。写 `simple_demo.#.heartbeat` 时，RabbitMQ 能匹配 `simple_demo.a.b.heartbeat`，NATS 不能。

**2. NATS 的 `>` 不会被转换，但只能是最后一个 token**

`foo.>` 合法；`foo.>.bar` 非法且 NATS 服务器会拒绝该订阅。框架不做校验，错误来自 NATS 服务端。

**3. 默认无持久化**

不使用 JetStream 时，NATS 与 Redis pub/sub 一样是 fire-and-forget。新订阅者拿不到历史。

**4. `identifier` 仅 facility 使用**

广播模式下 topic 由函数参数给出，locator 的 `identifier` 不被使用。与 Redis 的情况相同。

**5. TLS 证书需要三个属性齐全**

与 Redis 一致（`src/nats/NATSComponent.cpp:20–22`）：`ca_cert`、`client_cert`、`client_key` 分别读取，三个都给才建立完整 mTLS。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| libnats（nats.c） | **`libnats_static`** | NATS C 客户端 | https://github.com/nats-io/nats.c · https://docs.nats.io/ |
| OpenSSL | 传递依赖 | TLS | https://www.openssl.org/ |

`tm_transport/meson.build:18` 声明 `libnats_dep = dependency('libnats')`。

> ⚠️ **本环境的 `.pc` 修补**：`libnats.pc` 中的 `-lnats` 被改为 `-lnats_static`，因为安装的静态库文件名是 `libnats_static.a`，`-lnats` 会产生 "cannot find -lnats" 链接错误。详见仓库根 `CLAUDE.md` 的 "Known Build Issues & Fixes" 第 7 条。

## 相关章节

- [广播](../01-broadcast.md) — 通用广播接口与 topic 通配适配表
- [远程设施](../02-facilities.md) — facility 客户端设置
- [各传输能力矩阵](../00-overview.md)
- [Redis 传输](redis.md) — 定位相近（轻量 pub/sub，无持久化）
