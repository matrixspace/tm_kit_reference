---
title: aeron_ipc 传输
library: tm_transport
headers: [tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp, tm_kit/transport/aeron_ipc/AeronIpcImporterExporter.hpp]
keywords: [aeron_ipc, AeronIpcComponent, AeronIpcImporterExporter, Aeron, aeron:ipc, ExclusivePublication, media driver, 嵌入式 driver, TM_KIT_TRANSPORT_AERON_IPC, 同机进程间, SPMC, 低延迟, tether, backPressure, joinLatest, AeronIpcPublisherStats, AeronIpcSubscriberStats]
---

# aeron_ipc 传输

## 用途

基于 Aeron `aeron:ipc` 通道的**同机单发布者 / 多读者**广播（Linux only）。底层是 Aeron `ExclusivePublication`，由 Aeron media driver 管理共享内存日志缓冲。

适合：已经在用 Aeron 生态、或希望用成熟的 driver 管理读者生命周期（未 tether 的慢读者会被剔除）的同机低延迟场景。

不适合：跨机（本组件只用 `aeron:ipc`，不走 UDP）；不支持 facility。

与 [shm_seqlock](shm_seqlock.md)、[shm_cursor](shm_cursor.md) 的区别：后两者是 tm_transport 自带的裸共享内存环，零外部依赖；aeron_ipc 依赖 Aeron 库与 media driver（可嵌入）。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp>
#include <tm_kit/transport/aeron_ipc/AeronIpcImporterExporter.hpp>

namespace dev::cd606::tm::transport::aeron_ipc
```

**条件编译**：只有构建时找到 Aeron（以及 `uuid`）才会编译 aeron_ipc，并全局定义 `TM_KIT_TRANSPORT_AERON_IPC=1`（`tm_transport/meson.build:54`–`:63`）。该宏也写进生成的 `.pc` 的 cflags（`tm_transport/src/meson.build:33`–`:42`），下游通过 pkg-config 取得。所有共享头文件里对 aeron_ipc 的引用都包在 `#ifdef __linux__` + `#ifdef TM_KIT_TRANSPORT_AERON_IPC` 内。

## 核心类型与签名

### 1. `AeronIpcComponent`（`tm_transport/tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp:76`）

```cpp
class AeronIpcComponent {
public:
    struct NoTopicSelection {};
    uint32_t aeron_ipc_addSubscriptionClient(ConnectionLocator const &locator,
                    std::variant<NoTopicSelection, std::string, std::regex> const &topic,
                    std::function<void(basic::ByteDataWithTopic &&)> client,
                    std::optional<WireToUserHook> wireToUserHook = std::nullopt);
    void aeron_ipc_removeSubscriptionClient(uint32_t id);
    std::function<void(basic::ByteDataWithTopic &&)> aeron_ipc_getPublisher(ConnectionLocator const &locator, std::optional<UserToWireHook> userToWireHook = std::nullopt);
    std::unordered_map<ConnectionLocator, std::thread::native_handle_type> aeron_ipc_threadHandles();
    std::optional<AeronIpcPublisherStats> aeron_ipc_publisherStats(ConnectionLocator const &locator);
    std::optional<AeronIpcSubscriberStats> aeron_ipc_subscriberStats(ConnectionLocator const &locator);
};
```

统计结构（`AeronIpcComponent.hpp:60`、`:68`），计数器由发布/轮询线程用 relaxed atomic 写入：

| `AeronIpcPublisherStats` | 含义 |
|---|---|
| `published` | 成功发布数 |
| `notConnected` | 无读者连接，消息丢弃 |
| `backPressured` | 慢读者（尚未被剔除）导致 claim 被拒 |
| `adminAction` | term 轮转，立即重试 |
| `oversized` | 超过 `slotSize`，丢弃 |
| `failed` | publication 关闭或其他错误 |

| `AeronIpcSubscriberStats` | 含义 |
|---|---|
| `delivered` | 已解码并交给 client 的分片数 |
| `imagesJoined` | 见到的发布者 session（image）数 |
| `skippedOnJoin` | `joinLatest` 丢弃的积压分片数 |
| `clientRebuilds` | driver 消失后重建 Aeron client 的次数 |
| `malformed` | 格式错误的分片 |

### 2. Locator 语法（`AeronIpcComponent.hpp:24`–`:57`）

```
aeron_ipc://::::<name>[prop=value,prop=value,...]
```

`name` 经 32 位 FNV-1a 映射为 Aeron stream id，除非显式给 `stream`。

| 属性 | 含义 | 默认 |
|---|---|---|
| `dir` | Aeron 目录 | `AERON_DIR` 环境变量，否则 Aeron 的 `/dev/shm` 默认值 |
| `stream` | 显式 stream id | 由 name 哈希 |
| `slotSize` | 单条 topic+payload 最大字节数；超出则丢弃 | `1024` |
| `slotCount` | 每个 term 大约容纳多少条 `slotSize` 消息 | `8192` |
| `termLength` | 显式 term 长度（2 的幂，64KB..1GB），覆盖 `slotCount` | —— |
| `wait` | `spin` / `lowcpu` | `spin` |
| `spinCount` | 空轮询多少次后 PAUSE（spin）或睡眠（lowcpu） | spin `100000` / lowcpu `1000`（`src/aeron_ipc/AeronIpcComponent.cpp:834`） |
| `maxSleepUs` | lowcpu 模式最长睡眠 | `1000` |
| `joinLatest` | 读者首次看到发布者 session 时丢弃已提交积压，从最新消息开始 | `true` |
| `tether` | `false`：慢读者不能无限期拖住发布者 | `false` |
| `untetheredWindowLimitTimeoutMs` / `untetheredLingerTimeoutMs` / `untetheredRestingTimeoutMs` | 发布端，非 tether 读者的超时 | `10` / `10` / `100` |
| `backPressure` | `drop`：被背压的 claim 丢弃并计数；`retry`：自旋直到成功 | `drop` |
| `driver` | `auto` / `embedded` / `external`（仅发布端） | `auto` |
| `driverTimeoutMs` | driver 存活超时 | `5000` |
| `driverThreading` | `shared` / `shared_network` / `dedicated`（仅嵌入式 driver） | `shared` |
| `driverIdle` | `spin` / `noop` / `yield` / `backoff` / `sleeping`（仅嵌入式 driver） | `spin` |
| `driverTimerIntervalUs` | 嵌入式 driver 定时器间隔；非 tether 读者只在此定时器上检查 | `1000` |
| `driverCpu` | 嵌入式 driver 线程的 CPU 列表，如 `3`、`2:3`、`2-3` | `TM_AERON_IPC_DRIVER_CPU` 环境变量 |

注意属性分隔符：注释与测试里写的是 `[slotSize=256]` 这种方括号形式（`tm_transport/test/aeron_ipc_test/aeron_ipc_graph_test.cpp:10`）。

`slotSize` 上限：`kAeronMaxMtu - 4 - 32 = 65468` 字节（`src/aeron_ipc/AeronIpcComponent.cpp:30`–`:32`、`:145`），超出在构造时抛 `std::invalid_argument`。

### 3. 工厂：`AeronIpcImporterExporter<Env>`（`tm_transport/tm_kit/transport/aeron_ipc/AeronIpcImporterExporter.hpp:18`）

模板参数是 **`Env`**（要求 `std::is_base_of_v<AeronIpcComponent, Env>`，`:17`），与其他传输的 `<M>` 不同，`M` 在内部推出。

| 函数 | 行号 |
|---|---|
| `createImporter(locator, topic = NoTopicSelection(), wireToUserHook)` | `:21` |
| `createTypedImporter<T>(locator, topic, wireToUserHook)` | `:66` |
| `createExporter(locator, userToWireHook, heartbeatName = "")` | `:117` |
| `createTypedExporter<T>(locator, userToWireHook, heartbeatName)` | `:153` |
| `fetchFirstUpdateAndDisconnect(env, locator, topic, hook)` | `:192` |
| `fetchTypedFirstUpdateAndDisconnect<T>(env, locator, topic, predicate, hook)` | `:218` |

### 4. 接入 MultiTransport

- 枚举 `MultiTransportBroadcastListenerConnectionType::AeronIpc`、通道前缀 `"aeron_ipc"`（`tm_transport/tm_kit/transport/MultiTransportBroadcastListener.hpp:125`）。
- **不在 `AllNetworkTransportComponents` 里**（`MultiTransportBroadcastListener.hpp:38`），必须在 Environment 里显式列出 `aeron_ipc::AeronIpcComponent`。
- 心跳：`HeartbeatAndAlertComponentInitializer<Env, aeron_ipc::AeronIpcComponent>`（`tm_transport/tm_kit/transport/HeartbeatAndAlertComponent.hpp:251`）。

## 最小可用示例

示例代码库（`tm_examples/`）中暂无用例。下例节选自 tm_transport 自带测试：

```cpp
// 来源：tm_transport/test/aeron_ipc_test/aeron_ipc_graph_test.cpp:32（已简化）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>
    , infra::TrivialExitControlComponent
    , basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent, false>
    , transport::aeron_ipc::AeronIpcComponent
>;
using M = infra::RealTimeApp<Env>;
using R = infra::AppRunner<M>;

// 发布端
auto sink = transport::MultiTransportBroadcastPublisherManagingUtils<R>::oneByteDataBroadcastPublisher(
    r, "publisher", "aeron_ipc://::::graph_test[slotSize=256]");
r.connect(r.importItem("source", source), sink);

// 订阅端
auto source = transport::MultiTransportBroadcastListenerManagingUtils<R>::oneByteDataBroadcastListener(
    r, "listener", "aeron_ipc://::::graph_test[slotSize=256]", topic);
r.connect(std::move(source), r.exporterAsSink("sink", sink));
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓（仅 Linux、仅同机、需构建时找到 Aeron） | ✗ |
| 线程 | 每个订阅一个轮询线程；嵌入式 driver 另有自己的线程 | 不适用 |
| 慢读者 | 默认非 tether：被 driver 剔除；`backPressure=drop` 时发布端丢消息 | 不适用 |

## 易错点

**1. `TM_KIT_TRANSPORT_AERON_IPC` 未定义时一切静默消失**

没找到 Aeron 时，aeron_ipc 源文件不编译，共享头文件中的相关分支被 `#ifdef` 掉。此时 `aeron_ipc://` 通道仍能被 `parseMultiTransportBroadcastChannel` 解析（枚举无条件存在），但 Listener 里没有对应 `case`，不会建立订阅。下游自己的编译单元必须带上该宏（经 pkg-config 获得），否则头文件视图与库不一致。

**2. 发布前读者要先连上**

`joinLatest=true` 时读者从最新消息开始；没有读者连接时发布端计 `notConnected` 并丢弃。测试里发布端先 sleep 1 秒等读者（`aeron_ipc_graph_test.cpp:65`）。

**3. 发布函数只能单线程调用**

`AeronIpcComponent.hpp:57`：同一 locator 返回的 publisher 必须一次只被一个线程调用（底层是 `ExclusivePublication`）。没有 shm_seqlock / shm_cursor 那种 `writerLock` 开关；心跳与数据同发时需自行串行化。

**4. 嵌入式 driver 跟随发布进程**

`driver=auto` 在目录无活 driver 时嵌入一个（`src/aeron_ipc/AeronIpcComponent.cpp:362`–`:378`）。发布进程重启，driver 也随之消失；读者会一直重试并重建 client（`clientRebuilds` 计数）。生产环境可改用 `driver=external` 独立部署 media driver。

**5. `driverIdle=spin` 默认打满一个核**

嵌入式 driver 默认 spin 空闲策略，加上读者 `wait=spin`，一对发布/订阅至少占两个核。

**6. 超长消息被丢弃而不是报错**

运行期超过 `slotSize` 的消息只计 `oversized`，不抛异常。

## 第三方依赖

| 库 | 发现方式 | 用途 | 官方文档 |
|---|---|---|---|
| Aeron（`aeron_client_wrapper`、`aeron_static`、`aeron_driver_static`） | meson `dependency('aeron', method: 'cmake')` | publication / subscription / 嵌入式 media driver | https://github.com/real-logic/aeron/wiki |
| libuuid | `uuid` | Aeron driver 依赖 | —— |

## 相关章节

- [shm_seqlock 传输](shm_seqlock.md) / [shm_cursor 传输](shm_cursor.md) — 无外部依赖的同机共享内存方案
- [shared_memory_broadcast 传输](shared_memory_broadcast.md)
- [广播](../01-broadcast.md)
- [心跳与告警](../05-heartbeat-and-alert.md)
- [各传输能力矩阵](../00-overview.md)
