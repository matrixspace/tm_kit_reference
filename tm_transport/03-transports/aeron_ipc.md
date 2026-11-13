---
title: aeron_ipc 传输
library: tm_transport
headers: [tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp, tm_kit/transport/aeron_ipc/AeronIpcImporterExporter.hpp]
keywords: [aeron_ipc, AeronIpcComponent, AeronIpcImporterExporter, Aeron, aeron:ipc, ExclusivePublication, media driver, 嵌入式 driver, TM_KIT_TRANSPORT_AERON_IPC, 同机进程间, SPMC, 低延迟, tether, backPressure, joinLatest, AeronIpcPublisherStats, AeronIpcSubscriberStats, untetheredWindowLimitTimeoutMs, untetheredLingerTimeoutMs, overrun, driverCpu, driverBindFailed, cpu, 绑核, aeron_ipc_setThreadCpuLease, TM_AERON_IPC_DRIVER_CPU]
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

### 1. `AeronIpcComponent`（`tm_transport/tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp:95`）

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
    void aeron_ipc_setThreadCpuLease(ThreadCpuLeaseProvider provider);   // :117，poll 线程与 driver agent 绑核 provider，只能设一次
};
```

统计结构（`AeronIpcComponent.hpp:78`、`:87`），计数器由发布/轮询线程用 relaxed atomic 写入：

| `AeronIpcPublisherStats` | 含义 |
|---|---|
| `published` | 成功发布数 |
| `notConnected` | 无读者连接，消息丢弃 |
| `backPressured` | 慢读者（尚未被剔除）导致 claim 被拒 |
| `adminAction` | term 轮转，立即重试 |
| `oversized` | 超过 `slotSize`，丢弃 |
| `failed` | publication 关闭或其他错误 |
| `driverBindFailed` | 嵌入式 driver 的 agent 线程按 `driverCpu` 绑核失败的次数（driver 照常运行） |

| `AeronIpcSubscriberStats` | 含义 |
|---|---|
| `delivered` | 已解码并交给 client 的分片数 |
| `imagesJoined` | 见到的发布者 session（image）数 |
| `skippedOnJoin` | `joinLatest` 丢弃的积压分片数 |
| `clientRebuilds` | driver 消失后重建 Aeron client 的次数 |
| `malformed` | 格式错误的分片（topic 长度超出帧） |
| `overrun` | 帧头复核不一致、判定 term 已被复用而丢弃的分片数；大于 0 说明有回调长时间阻塞或超时参数设置过短 |

### 2. Locator 语法（`AeronIpcComponent.hpp:25`–`:75`）

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
| `spinCount` | 空轮询多少次后 PAUSE（spin）或睡眠（lowcpu） | spin `100000` / lowcpu `1000`（`src/aeron_ipc/AeronIpcComponent.cpp:868`） |
| `maxSleepUs` | lowcpu 模式最长睡眠 | `1000` |
| `joinLatest` | 读者首次看到发布者 session 时丢弃已提交积压，从最新消息开始 | `true` |
| `tether` | `false`：慢读者不能无限期拖住发布者 | `false` |
| `untetheredWindowLimitTimeoutMs` / `untetheredLingerTimeoutMs` / `untetheredRestingTimeoutMs` | 发布端，non-tether 读者的超时；总保护时间 = window-limit + linger，超时后读者被移出流控，publisher 可复用 term buffer。调大的代价见易错点 7 | `10` / `10` / `100` |
| `backPressure` | `drop`：被背压的 claim 丢弃并计数；`retry`：自旋直到成功 | `drop` |
| `driver` | `auto` / `embedded` / `external`（仅发布端） | `auto` |
| `driverTimeoutMs` | driver 存活超时 | `5000` |
| `driverThreading` | `shared` / `shared_network` / `dedicated`（仅嵌入式 driver） | `shared` |
| `driverIdle` | `spin` / `noop` / `yield` / `backoff` / `sleeping`（仅嵌入式 driver） | `spin` |
| `driverTimerIntervalUs` | 嵌入式 driver 定时器间隔；非 tether 读者只在此定时器上检查 | `1000` |
| `driverCpu` | 嵌入式 driver 的 agent 线程绑核，`CpuBindingSpec` 语法，如 `3`、`2:3`、`2-3`、`auto`、`numa:0`（旧写法仍有效）。需要 provider；失败计入 `driverBindFailed`，见易错点 8 | `TM_AERON_IPC_DRIVER_CPU` 环境变量；都没有时沿用 Aeron 的 `AERON_*_CPU_AFFINITY` |
| `cpu` | 本 locator 的订阅 poll 线程绑核，同样语法。每个完整 locator 一个 poll 线程，不与其他 locator 共享 | 不绑 |

注意属性分隔符：注释与测试里写的是 `[slotSize=256]` 这种方括号形式（`tm_transport/test/aeron_ipc_test/aeron_ipc_graph_test.cpp:10`）。

`slotSize` 上限：`kAeronMaxMtu - 4 - 32 = 65468` 字节（`src/aeron_ipc/AeronIpcComponent.cpp:32`–`:34`、`:147`），超出在构造时抛 `std::invalid_argument`。

### 3. 工厂：`AeronIpcImporterExporter<Env>`（`tm_transport/tm_kit/transport/aeron_ipc/AeronIpcImporterExporter.hpp:20`）

模板参数是 **`Env`**（要求 `std::is_base_of_v<AeronIpcComponent, Env>`，`:19`），与其他传输的 `<M>` 不同，`M` 在内部推出。

| 函数 | 行号 |
|---|---|
| `createImporter(locator, topic = NoTopicSelection(), wireToUserHook)` | `:23` |
| `createTypedImporter<T>(locator, topic, wireToUserHook)` | `:69` |
| `createExporter(locator, userToWireHook, heartbeatName = "")` | `:121` |
| `createTypedExporter<T>(locator, userToWireHook, heartbeatName)` | `:158` |
| `fetchFirstUpdateAndDisconnect(env, locator, topic, hook)` | `:198` |
| `fetchTypedFirstUpdateAndDisconnect<T>(env, locator, topic, predicate, hook)` | `:225` |

### 4. 接入 MultiTransport

- 枚举 `MultiTransportBroadcastListenerConnectionType::AeronIpc`、通道前缀 `"aeron_ipc"`（`tm_transport/tm_kit/transport/MultiTransportBroadcastListener.hpp:126`）。
- **不在 `AllNetworkTransportComponents` 里**（`MultiTransportBroadcastListener.hpp:39`），必须在 Environment 里显式列出 `aeron_ipc::AeronIpcComponent`。
- 心跳：`HeartbeatAndAlertComponentInitializer<Env, aeron_ipc::AeronIpcComponent>`（`tm_transport/tm_kit/transport/HeartbeatAndAlertComponent.hpp:252`）。

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
| 慢读者 | 默认非 tether：约 20ms（window-limit + linger）内被 driver 剔除；剔除前 `backPressure=drop` 时发布端丢消息 | 不适用 |

## 易错点

**1. `TM_KIT_TRANSPORT_AERON_IPC` 未定义时一切静默消失**

没找到 Aeron 时，aeron_ipc 源文件不编译，共享头文件中的相关分支被 `#ifdef` 掉。此时 `aeron_ipc://` 通道仍能被 `parseMultiTransportBroadcastChannel` 解析（枚举无条件存在），但 Listener 里没有对应 `case`，不会建立订阅。下游自己的编译单元必须带上该宏（经 pkg-config 获得），否则头文件视图与库不一致。

**2. 发布前读者要先连上**

`joinLatest=true` 时读者从最新消息开始；没有读者连接时发布端计 `notConnected` 并丢弃。测试里发布端先 sleep 1 秒等读者（`aeron_ipc_graph_test.cpp:65`）。

**3. 发布函数只能单线程调用**

`AeronIpcComponent.hpp:75`：同一 locator 返回的 publisher 必须一次只被一个线程调用（底层是 `ExclusivePublication`）。没有 shm_seqlock / shm_cursor 那种 `writerLock` 开关；心跳与数据同发时需自行串行化。

**4. 嵌入式 driver 跟随发布进程**

`driver=auto` 在目录无活 driver 时嵌入一个（`src/aeron_ipc/AeronIpcComponent.cpp:385`–`:401`）。发布进程重启，driver 也随之消失；读者会一直重试并重建 client（`clientRebuilds` 计数）。生产环境可改用 `driver=external` 独立部署 media driver。

**5. `driverIdle=spin` 默认打满一个核**

嵌入式 driver 默认 spin 空闲策略，加上读者 `wait=spin`，一对发布/订阅至少占两个核。

**6. 超长消息被丢弃而不是报错**

运行期超过 `slotSize` 的消息只计 `oversized`，不抛异常。

**7. 调大 untethered 超时会让所有读者一起丢消息**

默认 `untetheredWindowLimitTimeoutMs` / `untetheredLingerTimeoutMs` 为 10ms（`src/aeron_ipc/AeronIpcComponent.cpp:426`–`:428`）：慢读者约 20ms 内被移出流控，休息 `untetheredRestingTimeoutMs`（100ms）后重新加入，只丢它自己跟不上的消息。慢读者被移出之前一直占着窗口，发布端被背压；`backPressure=drop` 下这段时间的消息**所有读者（包括快读者）都收不到**。所以调大这两个值是用其他读者的投递换慢读者少丢——`05962f6` 曾把默认改成 2000ms，导致一个慢读者让快读者丢掉大部分消息，已在 tm_transport `8bb9d5c` 改回 10ms。只有“宁可拖慢全体也不想慢读者丢包”时才在 locator 上显式调大。

无论超时取多少，被移出时正在读的分片都不会以撕裂数据交付：handler 先把分片拷到线程私有缓冲再复核帧头，term 已被复用时丢弃并计入 `AeronIpcSubscriberStats::overrun`。

**8. `driverCpu` 失败不抛异常；dedicated 模式用 `auto`**

driver 的 agent 线程由 Aeron 的 C 回调启动，绑核失败只打 stderr 并计入 `AeronIpcPublisherStats::driverBindFailed`，driver 继续运行，部署后要看这个计数。属性语法错误或没有 provider 仍在 `getPublisher` 的调用线程抛 `std::invalid_argument`；`driverCpu=none` 不需要 provider。`driverThreading=dedicated` 时 3 个 agent 线程各取一次租约：`auto` 占 3 个核；显式 CPU 列表对每个 agent 是同一份，严格的分配器（hwloc）会拒绝第二次 reserve（计入 `driverBindFailed`），所以 dedicated 模式建议用 `auto`。`TM_AERON_IPC_DRIVER_CPU` 环境变量（locator 没写 `driverCpu` 时使用）现在也走 provider。provider 与 `cpu` 属性的通用规则见 [transport 线程绑核](../00-overview.md#6-transport-线程绑核)。

## 第三方依赖

| 库 | 发现方式 | 用途 | 官方文档 |
|---|---|---|---|
| Aeron（`aeron_client_wrapper`、`aeron_static`、`aeron_driver_static`） | meson `dependency('aeron', method: 'cmake')` | publication / subscription / 嵌入式 media driver | https://github.com/real-logic/aeron/wiki |
| libuuid | `uuid` | Aeron driver 依赖 | —— |

## 相关章节

- [各传输的并发支持](../08-concurrency.md) — 本传输的多进程 / 多线程读写结论
- [shm_seqlock 传输](shm_seqlock.md) / [shm_cursor 传输](shm_cursor.md) — 无外部依赖的同机共享内存方案
- [shared_memory_broadcast 传输](shared_memory_broadcast.md)
- [广播](../01-broadcast.md)
- [心跳与告警](../05-heartbeat-and-alert.md)
- [各传输能力矩阵](../00-overview.md) · [transport 线程绑核](../00-overview.md#6-transport-线程绑核)
