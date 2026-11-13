---
title: NNG 传输
library: tm_transport
headers: [tm_kit/transport/nng/NNGComponent.hpp, tm_kit/transport/nng/NNGImporterExporter.hpp]
keywords: [NNG, nanomsg-next-gen, NNGComponent, NNGImporterExporter, nngpp, ipc, tcp, 无 broker, 直连, pub sub, cpu, 绑核, nng_setThreadCpuLease]
---

# NNG 传输

## 用途

基于 [NNG](https://nng.nanomsg.org/)（nanomsg-next-generation）的**直连**广播传输。与 [ZeroMQ](zeromq.md) 定位相同：无 broker、低延迟、pub/sub 模式。

选它而非 ZeroMQ 通常是因为已有 NNG 基础设施，或偏好 NNG 的 API 与许可。两者在 TM Kit 里的能力完全相同——**都只支持广播，不支持 facility**。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/nng/NNGComponent.hpp>
#include <tm_kit/transport/nng/NNGImporterExporter.hpp>

namespace dev::cd606::tm::transport::nng
```

## 核心类型与签名

### 1. `NNGComponent`（`NNGComponent.hpp:23`）

Environment 组件。源码注释明确说明 locator 只需要 host 和 port：

```cpp
//NNGComponent.hpp:29 — "only host and port are needed in the locators"
struct NoTopicSelection {};

uint32_t nng_addSubscriptionClient(
    ConnectionLocator const &locator
    , std::variant<NoTopicSelection, std::string, std::regex> const &topic
    , std::function<void(basic::ByteDataWithTopic &&)> client
    , std::optional<WireToUserHook> wireToUserHook = std::nullopt
);
void nng_removeSubscriptionClient(uint32_t id);
std::function<void(basic::ByteDataWithTopic &&)> nng_getPublisher(
    ConnectionLocator const &locator
    , std::optional<UserToWireHook> userToWireHook = std::nullopt
);
std::unordered_map<ConnectionLocator, std::thread::native_handle_type> nng_threadHandles();
void nng_setThreadCpuLease(ThreadCpuLeaseProvider provider);   // :48，接收线程绑核 provider，只能设一次
```

### 2. Locator 语法

```
nng://host:port              # TCP 模式
nng://ipc:port:::identifier  # IPC 模式（identifier 作为路径）
```

`host` 有两类取值（`src/nng/NNGComponent.cpp:59`、`:254`）：

| `host` 取值 | 构造出的 NNG 地址 | 说明 |
|---|---|---|
| `ipc` | `ipc://<identifier>` | 同机进程间；`identifier` 是路径（`:60`） |
| 其他 | `tcp://<host>:<port>`（客户端，`:62`）<br>`tcp://*:<port>`（服务端，`:257`） | 网络模式 |

属性块只识别接收线程绑核属性 `cpu`（`CpuBindingSpec` 语法，不能含逗号，用区间；需要 provider，见 [transport 线程绑核](../00-overview.md#6-transport-线程绑核)）。接收线程按 host/port/identifier 共享，只认第一个 locator 的 `cpu`，之后的不同值只在 stderr 警告一次。NNG 传输不使用 `envelop`、`ignoreTopic` 等属性。

```
nng://ipc:0:::/tmp/feed[cpu=auto]
```

### 3. 工厂：`NNGImporterExporter<M>`（`NNGImporterExporter.hpp:20`）

```cpp
template <class M>
class NNGImporterExporter {
public:
    // :23 — topic 是 variant，支持 NoTopicSelection / 字符串 / 正则
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<NNGComponent::NoTopicSelection, std::string, std::regex> const &topic
            = NNGComponent::NoTopicSelection()
        , std::optional<WireToUserHook> wireToUserHook = std::nullopt
    );

    // :69
    template <class T>
    static std::shared_ptr<typename M::template Importer<basic::TypedDataWithTopic<T>>>
    createTypedImporter(...);

    // :121 / :158
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

NNG 在 `MultiTransportRemoteFacilityConnectionType`（`tm_kit/transport/MultiTransportRemoteFacility.hpp:41`）中没有对应项。

## 最小可用示例

`tm_examples/` 中暂无 NNG 的直接用例。按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/nng/NNGImporterExporter.hpp:23 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::nng::NNGComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;

// 发布：绑定本机 12346 端口
auto publisher = transport::nng::NNGImporterExporter<M>
    ::template createTypedExporter<TickData>(
        transport::ConnectionLocator::parse("0.0.0.0:12346"),
        std::nullopt,
        "tick publisher"
    );

// 订阅：只收 topic 匹配的消息
auto subscriber = transport::nng::NNGImporterExporter<M>
    ::template createTypedImporter<TickData>(
        transport::ConnectionLocator::parse("127.0.0.1:12346"),
        std::string("tick.btc"),
        std::nullopt
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 数据来源 | 直连 publisher 推送 | 文件 importer |
| 消息保留 | 无 | 文件完整 |
| topic 过滤 | **客户端**（NNG 本身不提供 pub/sub 过滤） | 文件格式自带 topic |
| 启动顺序 | 服务端（bind）必须先起 | 不适用 |

## 易错点

**1. 只能广播，不能做 facility**

需要请求-响应请用 `socket_rpc`、`grpc_interop`、RabbitMQ、Redis 或 NATS。

**2. `ipc` 模式的 `identifier` 才是地址，`port` 被忽略**

`host == "ipc"` 时构造的是 `ipc://<identifier>`（`src/nng/NNGComponent.cpp:60`），port 不参与。写 `nng://ipc:12345:::/tmp/my.sock` 时真正的地址是 `ipc:///tmp/my.sock`。

**3. topic 过滤在客户端，不省网络流量**

与 ZeroMQ 相同：所有消息都到达本进程，`topic` 参数只决定是否交给下游。

**4. `std::string` 类型的 topic 是精确匹配，不是前缀匹配**

与 ZeroMQ 的实现完全一致（`src/nng/NNGComponent.cpp:119` 的 `data.topic == std::get<0>(f)`；正则分支在 `:124`）。想匹配一类 topic 必须传 `std::regex`。这与 RabbitMQ（AMQP 通配）和 Redis（glob）的直觉相反。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| nngpp | `nngpp` | NNG 的 C++ 封装（内含 nng 本体） | https://github.com/nanomsg/nngpp |
| NNG 本体 | 由 nngpp 提供 | 底层消息库 | https://nng.nanomsg.org/ |

`tm_transport/meson.build:8` 声明 `nng_dep = [dependency('nngpp')]`。

## 相关章节

- [各传输的并发支持](../08-concurrency.md) — 本传输的多进程 / 多线程读写结论
- [广播](../01-broadcast.md) — 通用广播接口
- [ZeroMQ 传输](zeromq.md) — 能力完全对应，可互换
- [各传输能力矩阵](../00-overview.md) · [transport 线程绑核](../00-overview.md#6-transport-线程绑核)
