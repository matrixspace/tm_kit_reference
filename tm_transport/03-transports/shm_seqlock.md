---
title: shm_seqlock 传输
library: tm_transport
headers: [tm_kit/transport/shm_seqlock/ShmSeqlockComponent.hpp, tm_kit/transport/shm_seqlock/ShmSeqlockImporterExporter.hpp]
keywords: [shm_seqlock, ShmSeqlockComponent, ShmSeqlockImporterExporter, seqlock, 共享内存, SPMC, 单发布者多读者, 低延迟, /dev/shm, futex, layout, inline-premark, split, slotSize, slotCount, writerLock, join, ShmSeqlockReaderStats, ShmSeqlockPublisherStats, Linux, cpu, 绑核, shm_seqlock_setThreadCpuLease]
---

# shm_seqlock 传输

## 用途

**同机、Linux 专用**的单发布者多读者（SPMC）共享内存广播。段位于 `/dev/shm`，是一个由定长 slot 组成的环，每个 slot 由自己的序号保护（seqlock）。发布者从不等待读者；落后超过 `slotCount` 条的读者会被重新同步到最新消息，跳过的消息计为丢失。

适合：行情网关 → 多个策略进程这类"只要最新、宁丢不等"的低延迟场景。与 [shared_memory_broadcast](shared_memory_broadcast.md)（Boost.Interprocess）相比，它不依赖 Boost.Interprocess，延迟路径更短，并且提供丢包统计。

不适合：要求不丢消息的场景、跨机器、非 Linux 平台。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/shm_seqlock/ShmSeqlockComponent.hpp>
#include <tm_kit/transport/shm_seqlock/ShmSeqlockImporterExporter.hpp>

namespace dev::cd606::tm::transport::shm_seqlock
```

仅在 `__linux__` 下编译：`tm_transport/tm_kit/transport/meson.build` 与 `tm_transport/src/meson.build:26` 都以 `build_machine.system() == 'linux'` 为条件，共享头文件里的引用都用 `#ifdef __linux__` 包住。

## 核心类型与签名

### 1. `ShmSeqlockComponent`（`tm_transport/tm_kit/transport/shm_seqlock/ShmSeqlockComponent.hpp:107`）

```cpp
// tm_transport/tm_kit/transport/shm_seqlock/ShmSeqlockComponent.hpp:113-122
struct NoTopicSelection {};
uint32_t shm_seqlock_addSubscriptionClient(ConnectionLocator const &locator,
                std::variant<NoTopicSelection, std::string, std::regex> const &topic,
                std::function<void(basic::ByteDataWithTopic &&)> client,
                std::optional<WireToUserHook> wireToUserHook = std::nullopt);
void shm_seqlock_removeSubscriptionClient(uint32_t id);
std::function<void(basic::ByteDataWithTopic &&)> shm_seqlock_getPublisher(ConnectionLocator const &locator, std::optional<UserToWireHook> userToWireHook = std::nullopt);
std::unordered_map<ConnectionLocator, std::thread::native_handle_type> shm_seqlock_threadHandles();
std::unordered_map<ConnectionLocator, ShmSeqlockReaderStats> shm_seqlock_readerStats();
std::unordered_map<ConnectionLocator, ShmSeqlockPublisherStats> shm_seqlock_publisherStats();
void shm_seqlock_setThreadCpuLease(ThreadCpuLeaseProvider provider);   // :126，读线程绑核 provider，只能设一次
```

统计结构（`ShmSeqlockComponent.hpp:89`、`:98`）：

| 结构 | 字段 |
|---|---|
| `ShmSeqlockReaderStats` | `received`、`lost`、`lapResyncs`、`publisherRestarts`、`corrupt`、`reopens`、`splitLayout` |
| `ShmSeqlockPublisherStats` | `published`、`rejected`、`epoch`、`waiterResets`（futex 模式下清理的泄漏读者登记） |

### 2. Locator 语法

```
shm_seqlock://::::<segmentName>[prop=value,...]
```

只用 `identifier`（段名）和属性（`ShmSeqlockComponent.hpp:29`–`:30`）。段名必须非空且不含 `/`（`tm_transport/src/shm_seqlock/ShmSeqlockComponent.cpp:141`）。

发布端属性（决定段布局，`ShmSeqlockComponent.hpp:32`–`:59`）：

| 属性 | 含义 | 默认 |
|---|---|---|
| `slotSize` | 每 slot 可容纳的 topic+payload 字节数，1..2^26 | `1000` |
| `slotCount` | slot 数，2 的幂，2..2^24 | `4096` |
| `stride128` | slot 步长按 128 字节对齐 | 64 字节 |
| `layout` | `inline` / `split` / `inline-premark` | `inline` |
| `wait` | `futex` 时发布者唤醒 futex 等待的读者 | `spin` |
| `mlock` | 尽力 mlock 段 | `true` |
| `writerLock` | 串行化本进程多个线程对该段的 publish（如数据 + 心跳） | `false` |
| `testNoPremark` | **仅测试用**，关闭 pre-mark，不是合法 seqlock | —— |

读端属性（布局一律从段头读取，与 locator 写的无关，`:63`–`:83`）：

| 属性 | 含义 | 默认 |
|---|---|---|
| `read` | `classic`：自旋到 slot 就绪再拷贝；`spec`：先投机拷贝再校验（p50 更低但尾延迟和发布端开销更差） | `classic` |
| `wait` | `futex`：先自旋 `spinCount` 次再 `FUTEX_WAIT` | `spin` |
| `spinCount` | futex 模式下睡眠前的轮询次数 | `20000` |
| `futexTimeoutUs` | futex 等待超时（微秒） | `100000` |
| `pauseAfter` | spin 模式下空轮询 n 次后开始 PAUSE | `0`（从不） |
| `join` | `latest`：首条交付已发布的最新消息；`next`：只交付加入之后发布的 | `latest` |
| `mlock` | 尽力 mlock 映射 | `true` |
| `cpu` | 读线程绑核，`CpuBindingSpec` 语法（`none`/`auto`/`numa:<n>`/`cpus:<list>`/`<list>`，不能含逗号，用区间）。需要 provider，见 [transport 线程绑核](../00-overview.md#6-transport-线程绑核) | 不绑 |

`layout` 三种取值的区别（`:36`–`:51`）：

| layout | seq 位置 | 特点 |
|---|---|---|
| `inline` | 与 slot 头、前若干数据字节同一 64B 行 | 默认 |
| `split` | 独占一条 64B 行 | 每次提交后预标记（pre-mark）下一 slot，被轮询的行每条消息只写一次 |
| `inline-premark` | 同 `inline` | 也预标记下一 slot，并调整写序：先写 line 0 之外的字节，再把 line 0（长度 + topic 前缀 + 提交 seq）一次写完 |

`split` / `inline-premark` 下读者最多可落后 `slotCount-1` 条而不被套圈。

### 3. 工厂：`ShmSeqlockImporterExporter<Env>`（`ShmSeqlockImporterExporter.hpp:20`）

```cpp
// tm_transport/tm_kit/transport/shm_seqlock/ShmSeqlockImporterExporter.hpp:19-20
template <class Env, std::enable_if_t<std::is_base_of_v<ShmSeqlockComponent, Env>, int> = 0>
class ShmSeqlockImporterExporter {
```

注意模板参数是 **`Env`**（内部 `using M = infra::RealTimeApp<Env>`），不是 `M`。成员与其他广播传输一致：

| 函数 | 行号 |
|---|---|
| `createImporter(locator, topic = NoTopicSelection(), wireToUserHook)` | `:23` |
| `createTypedImporter<T>(...)` | `:69` |
| `createExporter(locator, userToWireHook, heartbeatName = "")` | `:121` |
| `createTypedExporter<T>(...)` | `:158` |
| `fetchFirstUpdateAndDisconnect(env, locator, topic, hook)` | `:198` |
| `fetchTypedFirstUpdateAndDisconnect<T>(env, locator, topic, predicate, hook)` | `:225` |

### 4. 接入 MultiTransport 层

连接类型名 `shm_seqlock`，枚举值 `MultiTransportBroadcastListenerConnectionType::ShmSeqlock`（`tm_transport/tm_kit/transport/MultiTransportBroadcastListener.hpp:124`）。已接入：

- `AllNetworkTransportComponents`（`MultiTransportBroadcastListener.hpp:48`）
- `MultiTransportBroadcastListener`、`MultiTransportBroadcastListenerManagingUtils`（含 SynchronousRunner 版本）、`MultiTransportBroadcastPublisherManagingUtils`
- 心跳：`HeartbeatAndAlertComponentInitializer<Env, shm_seqlock::ShmSeqlockComponent>`（`tm_transport/tm_kit/transport/HeartbeatAndAlertComponent.hpp:219`）
- 被视为"无需 topic 订阅"的类型，与 multicast、shared_memory_broadcast 同组（`MultiTransportBroadcastListener.hpp:166`）

## 最小可用示例

`tm_examples/` 中暂无用例。下面节选自 tm_transport 自带的测试：

```cpp
// 来源：tm_transport/test/shm_seqlock_test/ShmSeqlockTest.cpp:286（已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TrivialBoostLoggingComponent,
    basic::real_time_clock::ClockComponent,
    transport::shm_seqlock::ShmSeqlockComponent
>;
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

直接用组件 API 收发（不经过图）：

```cpp
// 来源：tm_transport/test/shm_seqlock_test/ShmSeqlockTest.cpp:202（已简化）
transport::shm_seqlock::ShmSeqlockComponent pubComp;
auto pub = pubComp.shm_seqlock_getPublisher(locator);

auto comp = std::make_unique<transport::shm_seqlock::ShmSeqlockComponent>();
comp->shm_seqlock_addSubscriptionClient(
    locator
    , transport::shm_seqlock::ShmSeqlockComponent::NoTopicSelection {}
    , [](basic::ByteDataWithTopic &&d) { /* ... */ }
);
```

经 MultiTransport 层时，channel 写成 `shm_seqlock://::::md[slotSize=512,slotCount=8192,layout=inline-premark]` 即可。

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓（仅同机、仅 Linux） | ✗ |
| 投递语义 | 有损：慢读者被套圈后跳到最新 | 不适用，回测用文件 importer |
| 线程 | 每段每个组件一条读线程 | —— |
| CPU | `wait=spin` 时读线程占满一个核；可用 `cpu` 属性把读线程绑到指定核 | —— |

## 易错点

**1. 有损，不是队列**

发布者从不等读者。落后超过 `slotCount`（`split`/`inline-premark` 下为 `slotCount-1`）的读者被重新同步，丢失计入 `ShmSeqlockReaderStats::lost`。需要可靠投递时不要用它，或者在应用层检测序号空洞。

**2. 同进程多线程发布必须开 `writerLock=true`**

一个段只能有一个发布者线程。跨进程由 `flock` 强制，**进程内不强制**（`ShmSeqlockComponent.hpp:85`–`:88`）。典型陷阱：数据和 `HeartbeatAndAlertComponent` 心跳发往同一段，两个线程并发调 publisher 会写坏消息。此时必须在 locator 上加 `writerLock=true`。

**3. 第一个订阅决定读者属性**

每个段在每个组件里只有一条读线程，读端属性（`read`、`wait`、`join` 等）由该段的**第一个订阅**决定，之后的订阅改属性无效。`cpu` 同理：读线程按第一个订阅的 `cpu` 绑核，之后的订阅写不同的值只在 stderr 警告一次。

**4. 读端 locator 里的布局属性被忽略**

读者一律按段头的布局读。发布端换了布局重启时，旧段被标为 superseded，读者自动重开新段；同布局重启则消息索引接续，读者无感恢复（`:60`–`:62`）。

**5. 超过 `slotSize` 的消息被拒绝**

topic+payload 超过 `slotSize` 时消息不会发出，计入 `ShmSeqlockPublisherStats::rejected`。按最大消息尺寸设置 `slotSize`。

**6. 容器内需要共享 `/dev/shm`**

与所有共享内存方案相同，跨容器通信要 `--ipc=host` 或共享的 tmpfs 挂载。

**7. 不支持 facility**

只能广播。请求-响应见 [socket_rpc](socket_rpc.md) 等。

## 第三方依赖

无。直接使用 Linux 系统调用（`mmap`、`flock`、`futex`、`mlock`）。

## 相关章节

- [各传输的并发支持](../08-concurrency.md) — 本传输的多进程 / 多线程读写结论
- [shm_cursor 传输](shm_cursor.md) — 同为 Linux SPMC 共享内存，全局游标设计
- [aeron_ipc 传输](aeron_ipc.md) — 基于 Aeron 媒体驱动的 IPC
- [shared_memory_broadcast 传输](shared_memory_broadcast.md) — 跨平台的 Boost.Interprocess 方案
- [广播](../01-broadcast.md) · [能力矩阵](../00-overview.md)
- [心跳与告警](../05-heartbeat-and-alert.md)
