---
title: shm_cursor 传输
library: tm_transport
headers: [tm_kit/transport/shm_cursor/ShmCursorComponent.hpp, tm_kit/transport/shm_cursor/ShmCursorImporterExporter.hpp]
keywords: [shm_cursor, ShmCursorComponent, ShmCursorImporterExporter, 共享内存, 全局游标, SPMC, 有损, 低延迟, /dev/shm, futex, slotSize, slotCount, publisherLock, join, subscriptionLossCount, subscriptionOverwriteCount, publisherRejectedCount, Linux]
---

# shm_cursor 传输

## 用途

**同机、Linux 专用**的有损单发布者多读者（SPMC）共享内存传输，用一个全局游标标记最新提交位置。读者落后或在拷贝过程中 slot 被覆盖时丢消息并计数，发布者不等任何读者。

和 [shm_seqlock](shm_seqlock.md) 的定位相近，区别在实现：shm_cursor 用全局游标，接口更简单，统计按 locator 单独查询。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/shm_cursor/ShmCursorComponent.hpp>
#include <tm_kit/transport/shm_cursor/ShmCursorImporterExporter.hpp>

namespace dev::cd606::tm::transport::shm_cursor
```

仅在 `__linux__` 下编译（`tm_transport/src/meson.build:28`）。

## 核心类型与签名

### 1. `ShmCursorComponent`（`tm_transport/tm_kit/transport/shm_cursor/ShmCursorComponent.hpp:51`）

```cpp
// tm_transport/tm_kit/transport/shm_cursor/ShmCursorComponent.hpp:58-75
struct NoTopicSelection {};
uint32_t shm_cursor_addSubscriptionClient(ConnectionLocator const &locator,
    std::variant<NoTopicSelection, std::string, std::regex> const &topic,
    std::function<void(basic::ByteDataWithTopic &&)> client,
    std::optional<WireToUserHook> wireToUserHook = std::nullopt);
void shm_cursor_removeSubscriptionClient(uint32_t id);
std::function<void(basic::ByteDataWithTopic &&)> shm_cursor_getPublisher(ConnectionLocator const &locator, std::optional<UserToWireHook> userToWireHook = std::nullopt);
std::unordered_map<ConnectionLocator, std::thread::native_handle_type> shm_cursor_threadHandles();
uint64_t shm_cursor_subscriptionLossCount(ConnectionLocator const &locator);
uint64_t shm_cursor_subscriptionOverwriteCount(ConnectionLocator const &locator);
uint64_t shm_cursor_publisherRejectedCount(ConnectionLocator const &locator);
```

| 统计 | 含义 |
|---|---|
| `subscriptionLossCount` | 本进程读者丢失的消息数（被套圈或拷贝中被覆盖），未订阅时为 0 |
| `subscriptionOverwriteCount` | 读者检测到正在拷贝的 slot 被覆盖的次数（也计入 loss） |
| `publisherRejectedCount` | topic+payload 超过 slot 容量而被拒的消息数 |

### 2. Locator 语法

```
shm_cursor://::::<segmentName>[prop=value,...]
```

段名 1–200 字符，只能含字母、数字、`_`、`-`、`.`（`tm_transport/src/shm_cursor/ShmCursorComponent.cpp:94`、`:98`）。属性（`ShmCursorComponent.hpp:23`–`:38`）：

| 属性 | 适用端 | 含义 | 默认 |
|---|---|---|---|
| `slotSize` | 发布 | 每 slot 字节数，64 的倍数，64..2^30；单条消息 topic+payload 最多 `slotSize-16` | `1024` |
| `slotCount` | 发布 | slot 数，2 的幂，2..2^30 | `4096` |
| `wait` | 两端 | `spin` / `futex`；发布端 futex 开启唤醒，读端 futex 为先自旋后睡眠 | `spin` |
| `spinCount` | 读，futex | 睡眠前空轮询次数 | `20000` |
| `pauseAfter` | 读，spin | 空轮询多少次后开始用 PAUSE | `100000` |
| `futexTimeoutMs` | 读，futex | 单次 futex 等待上限（毫秒） | `10` |
| `join` | 读 | `latest`：首条为加入时最后提交的那条；`next`：只要加入后提交的 | `latest` |
| `publisherLock` | 发布 | 本进程多线程发布同一段时设为 `true` | `false` |

非法取值直接抛 `std::runtime_error`（如 `ShmCursorComponent.cpp:127`、`:141`、`:149`、`:152`、`:155`）。

### 3. 工厂：`ShmCursorImporterExporter<Env>`（`ShmCursorImporterExporter.hpp:18`）

模板参数同样是 **`Env`**，要求 `std::is_base_of_v<ShmCursorComponent, Env>`（`:17`）。

| 函数 | 行号 |
|---|---|
| `createImporter(locator, topic = NoTopicSelection(), wireToUserHook)` | `:21` |
| `createTypedImporter<T>(...)` | `:67` |
| `createExporter(locator, userToWireHook, heartbeatName = "")` | `:119` |
| `createTypedExporter<T>(...)` | `:155` |
| `fetchFirstUpdateAndDisconnect(env, locator, topic, hook)` | `:194` |
| `fetchTypedFirstUpdateAndDisconnect<T>(env, locator, topic, predicate, hook)` | `:217` |

### 4. 接入 MultiTransport 层

连接类型名 `shm_cursor`，枚举 `MultiTransportBroadcastListenerConnectionType::ShmCursor`（`tm_transport/tm_kit/transport/MultiTransportBroadcastListener.hpp:124`）。已在 `AllNetworkTransportComponents`（`:48`）中，监听/发布 ManagingUtils 与心跳（`tm_transport/tm_kit/transport/HeartbeatAndAlertComponent.hpp:234`）均已支持。

## 最小可用示例

`tm_examples/` 中暂无用例。下面节选自 tm_transport 自带测试：

```cpp
// 来源：tm_transport/test/shm_cursor_test/shm_cursor_test.cpp:52
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TrivialBoostLoggingComponent,
    basic::real_time_clock::ClockComponent,
    transport::BoostUUIDComponent,
    transport::AllNetworkTransportComponents,
    transport::HeartbeatAndAlertComponent>;
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
```

心跳走 shm_cursor：

```cpp
// 来源：tm_transport/test/shm_cursor_test/shm_cursor_test.cpp:210
transport::initializeHeartbeatAndAlertComponent(&env, "shm_cursor_test_pub", heartbeatChannel);
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓（仅同机、仅 Linux） | ✗ |
| 投递语义 | 有损，读者最多看到 `join=latest` 时的那一条历史 | 不适用 |
| CPU | `wait=spin` 时读线程持续占核 | —— |

## 易错点

**1. 第一个 locator 决定段属性**

只用 `identifier` 作段的键，本进程**第一个**见到的 locator 决定该段的属性（`ShmCursorComponent.hpp:40`–`:44`）。后续 locator 写不同属性不生效。

**2. 发布端改布局会重建段**

`slotSize`/`slotCount` 只在发布端有意义。发布者布局与现有段不同时会重建段；读者总从段头取布局。

**3. 一个段只能有一个发布进程**

由 `/dev/shm/tm_shm_cursor.<name>.lock` 上的独占 `flock` 强制（`:45`–`:48`）。同进程多线程发布（例如数据 + 心跳发往同一段）必须加 `publisherLock=true`，否则并发调用会写坏数据。

**4. 与 `MultiTransportBroadcastFirstUpdateQueryManagingUtils` + `AllNetworkTransportComponents` 一起用编译不过**

测试注释指出：`WebSocketImporterExporter::fetchFirstUpdateAndDisconnect` 里的 `websocket_addSubscriptionClient` 调用有歧义（与 shm_cursor 无关的旧问题），所以 fetch 路径要用只含所需传输的 Environment（`tm_transport/test/shm_cursor_test/shm_cursor_test.cpp:62` 附近，之后的 `FetchEnvironment` 在 `:67`）。

**5. 消息上限是 `slotSize-16`，不是 `slotSize`**

slot 里有 16 字节头。超限消息被拒，计入 `publisherRejectedCount`。

**6. 不支持 facility；容器内需共享 `/dev/shm`**

## 第三方依赖

无。直接使用 Linux 系统调用（`mmap`、`flock`、`futex`）。

## 相关章节

- [shm_seqlock 传输](shm_seqlock.md) — 每 slot seqlock 设计，统计更细
- [aeron_ipc 传输](aeron_ipc.md)
- [shared_memory_broadcast 传输](shared_memory_broadcast.md)
- [广播](../01-broadcast.md) · [能力矩阵](../00-overview.md) · [心跳与告警](../05-heartbeat-and-alert.md)
