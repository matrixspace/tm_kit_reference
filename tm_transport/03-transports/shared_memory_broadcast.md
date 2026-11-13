---
title: SharedMemoryBroadcast 传输
library: tm_transport
headers: [tm_kit/transport/shared_memory_broadcast/SharedMemoryBroadcastComponent.hpp, tm_kit/transport/shared_memory_broadcast/SharedMemoryBroadcastImporterExporter.hpp]
keywords: [shared_memory_broadcast, SharedMemoryBroadcastComponent, SharedMemoryBroadcastImporterExporter, 共享内存, Boost.Interprocess, 同机进程间, size, busyLoop, 零拷贝, 低延迟, cpu, 绑核, shared_memory_broadcast_setThreadCpuLease, threadHandles, 取消订阅]
---

# SharedMemoryBroadcast 传输

## 用途

**同机进程间**通过共享内存做广播。没有网络栈、没有序列化到 socket 的开销，是同机多进程通信中延迟最低的方案。

适合：同一台机器上的行情网关 → 多个策略进程、风控前置 → 执行进程等对延迟极敏感的场景。

不适合：跨机器（共享内存只在同一内核内可见）。

**注意**：这条路径上的数据仍会经过序列化（写入共享内存的是字节流），只是省掉了内核网络协议栈的开销。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/shared_memory_broadcast/SharedMemoryBroadcastComponent.hpp>
#include <tm_kit/transport/shared_memory_broadcast/SharedMemoryBroadcastImporterExporter.hpp>

namespace dev::cd606::tm::transport::shared_memory_broadcast
```

## 核心类型与签名

### 1. `SharedMemoryBroadcastComponent`（`SharedMemoryBroadcastComponent.hpp`）

Environment 组件（`SharedMemoryBroadcastComponent.hpp:23`）。提供 `shared_memory_broadcast_threadHandles()` 用于诊断（返回有效的接收线程 native handle，可直接用于 `pthread_getaffinity_np` 等），`struct NoTopicSelection {}`，以及接收线程绑核 provider 的注入接口：

```cpp
void shared_memory_broadcast_setThreadCpuLease(ThreadCpuLeaseProvider provider);   // :49，只能设一次，第二次抛 std::logic_error
```

### 2. Locator 语法

```
shared_memory_broadcast://:::sharedMemoryName[size=4294967296][busyLoop=false][cpu=none]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` / `port` | **未使用** | —— |
| `identifier` | **共享内存段名**（`src/shared_memory_broadcast/SharedMemoryBroadcastComponent.cpp:247`、`:520`） | —— |
| `size` | 共享内存段大小（字节） | **4 GiB**（`4*1024*1024*1024`，`:688`、`:717`） |
| `busyLoop` | 为 `true` 时用忙等而非阻塞等待（更低延迟、更高 CPU） | `false`（`:689`） |
| `cpu` | 接收线程绑核，`CpuBindingSpec` 语法（不能含逗号，用区间）。接收线程按段名共享，只认第一个 locator 的值，之后的不同值只警告一次。需要 provider，见 [transport 线程绑核](../00-overview.md#6-transport-线程绑核) | 不绑 |

**`identifier` 是唯一的定位字段**，必须写在第 5 段。典型写法：`shared_memory_broadcast://:::market_data`。

### 3. 工厂：`SharedMemoryBroadcastImporterExporter<M>`（`SharedMemoryBroadcastImporterExporter.hpp:20`）

```cpp
template <class M>
class SharedMemoryBroadcastImporterExporter {
public:
    // :23
    static std::shared_ptr<typename M::template Importer<basic::ByteDataWithTopic>>
    createImporter(
        ConnectionLocator const &locator
        , std::variant<SharedMemoryBroadcastComponent::NoTopicSelection, std::string, std::regex> const &topic
            = SharedMemoryBroadcastComponent::NoTopicSelection()
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

`MultiTransportRemoteFacilityConnectionType`（`tm_kit/transport/MultiTransportRemoteFacility.hpp:41`）中没有 shared_memory_broadcast 项。

## 最小可用示例

`tm_examples/` 中暂无 shared_memory_broadcast 的直接用例。按头文件签名构造的最小骨架：

```cpp
// 来源：tm_kit/transport/shared_memory_broadcast/SharedMemoryBroadcastImporterExporter.hpp:23 签名（示例代码库中暂无用例）
using Env = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::shared_memory_broadcast::SharedMemoryBroadcastComponent,
    transport::BoostUUIDComponent
>;
using M = infra::RealTimeApp<Env>;

// 发布：写入名为 market_data 的共享内存段，段大小 8 GiB，忙等模式
auto publisher = transport::shared_memory_broadcast::SharedMemoryBroadcastImporterExporter<M>
    ::template createTypedExporter<TickData>(
        transport::ConnectionLocator::parse(
            ":::market_data[size=8589934592,busyLoop=true]"
        ),
        std::nullopt,
        "tick publisher"
    );

// 订阅：同一段名
auto subscriber = transport::shared_memory_broadcast::SharedMemoryBroadcastImporterExporter<M>
    ::template createTypedImporter<TickData>(
        transport::ConnectionLocator::parse(":::market_data[size=8589934592]"),
        std::string("tick.btc"),
        std::nullopt
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓（仅同机） | ✗ |
| 数据来源 | 共享内存环形缓冲 | 文件 importer |
| 延迟 | 最低（无网络栈） | 不适用 |
| CPU | `busyLoop=true` 时持续占用一个核；可用 `cpu` 属性绑到指定核 | 不适用 |
| 消息保留 | 环形缓冲，被覆盖即丢失 | 文件完整 |

## 易错点

**1. `identifier` 必须写在第 5 段，前 4 段留空**

locator 用 `identifier` 作共享内存段名（`:247`、`:520`），而 `identifier` 是 `parse` 的第 5 段。写成 `shared_memory_broadcast://market_data` 会把 `market_data` 当作 **host**，段名变成空串。正确写法是 `shared_memory_broadcast://:::market_data`（三个冒号跳过 host/port/user/pass）。

**2. `size` 默认 4 GiB，会真实占用（或预留）这么多地址空间**

`std::stoul(d.query("size", std::to_string(4*1024*1024*1024UL)))`（`:688`）。在 32 位进程或内存受限容器里会直接失败。生产环境应按实际峰值流量显式指定 `size`。

**3. 收发两端的 `size` 必须一致**

共享内存段的创建参数由**第一个**创建者决定。如果发布端用默认 4 GiB、订阅端用 1 GiB，订阅端打开已存在的段时参数不匹配，行为未定义（取决于 Boost.Interprocess 的检查）。所有进程应使用完全相同的 locator 属性。

**4. `busyLoop=true` 会打满一个 CPU 核**

`busyLoop` 默认 `false`（`:689`），用阻塞等待。设为 `true` 能降低消息到达的感知延迟，但会持续占用一个核心。多进程大量使用时需要评估 CPU 预算。

**5. 进程崩溃可能留下残留的共享内存段**

与所有共享内存方案一样，进程异常退出可能留下已命名的段。下次启动时若 `size` 与残留段不一致会失败。清理需要手动删除 `/dev/shm/` 下的对应文件（Linux）。

**6. 仅同机可用**

`host`/`port` 被忽略，共享内存只在同一内核内可见。容器化部署时，**不同容器默认不共享 `/dev/shm`**，除非显式配置 `--ipc=host` 或共享的 tmpfs 挂载。

**7. 不支持 facility**

需要请求-响应请用 `socket_rpc` 或其他支持 facility 的传输。

**8. 取消订阅会等接收线程退出**

接收线程在取消订阅（订阅对象析构）时被 join，之后才释放共享内存（`src/shared_memory_broadcast/SharedMemoryBroadcastComponent.cpp:344`–`:351`）；阻塞等待模式（`busyLoop=false`）下最长约 1 秒。旧版本把线程 detach 后立即释放共享内存，取消订阅时可复现 use-after-free / SIGSEGV。订阅销毁在组件锁之外进行，回调里重入组件不会死锁；从该订阅自己的回调里取消时退化为 detach。

另外，读者切换链尾（`swapTail()`，`:148`）现在在跨进程的 `listMutex` 下进行，修复了发布者对已释放链尾节点做 CAS 的竞争（表现为 SIGSEGV 或消息丢失）；共享内存布局不变。详见 tm_transport 仓库的 `doc/20261112-ipc-thread-affinity/README.md`。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| Boost.Interprocess | `boost` | 共享内存段与进程间同步原语 | https://www.boost.org/doc/libs/release/doc/html/interprocess.html |

`tm_transport` 整体做了 Boost 版本的兼容处理：源码中大量出现 `#if BOOST_VERSION >= 108700` 之类的分支（`src/multicast/MulticastComponent.cpp` 单文件就有 12 处），用于在 `io_context` / `io_service` 等 API 变更处选择正确写法。这意味着框架可以同时构建在旧版（Boost 1.7x 及更早）与新版（Boost 1.87+）Boost 上，但**行为细节可能因 Boost 版本而异**——同一份代码在不同 Boost 版本下编译出的二进制不应假设行为完全一致。见仓库根 `CLAUDE.md` 的依赖清单（Boost 1.91.0）。

## 相关章节

- [各传输的并发支持](../08-concurrency.md) — 本传输的多进程 / 多线程读写结论
- [广播](../01-broadcast.md) — 通用广播接口
- [multicast 传输](multicast.md) — 跨机的低延迟替代方案
- [ZeroMQ 传输](zeromq.md) — 支持 IPC（`ipc://`）的同机方案
- [shm_seqlock 传输](shm_seqlock.md) / [shm_cursor 传输](shm_cursor.md) / [aeron_ipc 传输](aeron_ipc.md) — Linux 下更低延迟的同机 SPMC 方案
- [各传输能力矩阵](../00-overview.md) · [transport 线程绑核](../00-overview.md#6-transport-线程绑核)
