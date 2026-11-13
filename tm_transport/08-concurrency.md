---
title: 各传输的并发支持
library: tm_transport
headers: [tm_kit/transport/MultiTransportBroadcastPublisherManagingUtils.hpp, tm_kit/transport/HeartbeatAndAlertComponent.hpp, tm_kit/transport/shm_seqlock/ShmSeqlockComponent.hpp, tm_kit/transport/shm_cursor/ShmCursorComponent.hpp, tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp]
keywords: [并发, 线程安全, thread safety, 多进程, 多线程, 多写者, 多读者, publisher, exporter, 心跳, writerLock, publisherLock, 死锁, deadlock, use-after-free, 负载均衡, load balancing, 并发矩阵]
---

# 各传输的并发支持

## 用途

回答四个问题：同一信道能否**多进程写**、**多进程读**，同一进程内能否**多线程写**、**多线程读**。facility 传输另外回答多 server 进程、client 多线程调用、server 跨线程回复。

结论来自阅读 `tm_transport` 源码（行号对应 tm_transport `develop` @ `ccb9a8c`）。四种同机 IPC 传输（`shm_seqlock`、`shm_cursor`、`aeron_ipc`、`shared_memory_broadcast`）另有并发压测 `tm_transport/test/ipc_concurrency_test/`，结论标"实测"；网络和 broker 类传输只读了代码，标"潜在风险"的条目是代码层面可以构造出的竞争，未实测复现。

压测与修复记录见 tm_transport 仓库的 `doc/20261103-ipc-concurrency-test/README.md` 和 `doc/20261103-ipc-concurrency-bugfix/README.md`；`shared_memory_broadcast` 读者竞争、取消订阅 use-after-free 的修复与 aeron_ipc untethered 默认值的回退见 `doc/20261112-ipc-thread-affinity/README.md` 和 `doc/20261113-aeron-untethered-defaults/README.md`。

## 发布函数为什么会被多线程调用

`createExporter` / `createTypedExporter` 返回的 `LocalE` 是普通 `AbstractExporter`，不是 `ThreadedHandler`，`handle()` 直接在上游线程里调 `publisher_`（例如 `tm_transport/tm_kit/transport/shm_seqlock/ShmSeqlockImporterExporter.hpp:151`）。以下三种情况会让同一个底层 sender 被多个线程同时调用：

1. **一个 sink 连了多个上游**。`MultiTransportBroadcastPublisherManagingUtils::oneBroadcastPublisher` 默认 `threaded=false`，每个上游线程都直接进 publisher。
2. **心跳 / 告警与数据共用 locator**。`HeartbeatAndAlertComponentInitializer` 对同一 locator 调 `xxx_getPublisher`（`tm_transport/tm_kit/transport/HeartbeatAndAlertComponent.hpp:219`）。大部分组件按 locator（或其一部分）复用 sender，心跳在时钟 importer 线程发布，`sendAlert` 可来自任意线程，publisher 调用本身不加锁（`tm_transport/src/HeartbeatAndAlertComponent.cpp:56`、`:82`）。
3. **同进程两个 exporter 指向同一信道**。

图内的情况 1 可以用 `oneBroadcastPublisher(..., threaded=true)` 解决：它在 exporter 前插入一个 threaded 的 id kleisli，默认把所有上游串行到专用线程；选 SharedPool 时是同一 strand，仍串行但不固定线程。显式选 Inline 则不能据此保证串行。**它管不到情况 2**。

上述 `threaded=true` 的串行化结论适用于默认 Dedicated 和保证 `kSerialCallbacks=true` 的执行器。handler 扩展点也影响 gRPC / JSON REST 客户端的请求处理上下文，不替换传输组件自身的 IO 线程；并发矩阵中的客户端安全结论不能直接推广到自定义非串行执行器。见 [实时执行器参考](../tm_infra/10-realtime-executors.md)。本次合并只增加 / 调整 transport 回归测试，没有修改传输协议实现；本轮文档同步未重跑网络测试。

## 广播传输并发矩阵

| 传输 | 多进程写 | 多进程读 | 进程内多线程写 | 进程内多线程读 | 数据与心跳共用 locator |
|---|---|---|---|---|---|
| `shm_seqlock` | ✗ `flock` 强制单发布进程 | ✓ | ✗ 默认；`writerLock=true` 后 ✓ | ✓ 每段一条读线程 | ✗ 除非**所有** locator 都带 `writerLock=true` |
| `shm_cursor` | ✗ `flock` 强制单发布进程 | ✓ | ✗ 默认；`publisherLock=true` 后 ✓ | ✓ 每段一条读线程 | ✗ 除非**所有** locator 都带 `publisherLock=true` |
| `aeron_ipc` | ⚠ 可以，每进程一个 session，跨发布者无序 | ✓ | ✗ 无开关 | ✓ 每 locator 一条轮询线程；回调勿长时间阻塞 | ✗ |
| `shared_memory_broadcast` | ⚠ 段不排他，未实测出问题，不建议 | ✓ 每读者独立队列 | ✓ `publish` 持 `listMutex`；读者竞争已修复（实测） | ✓ 多读者组件已修复 | ✓ 同多线程写 |
| `multicast` | ✓ 跨发送者无序 | ✓ `reuse_address` | ✓ 发送端加锁 | ✓ | ✓ |
| `singlecast` | ✓ 跨发送者无序 | ✗ 端口只能一个读进程 | ✗ 无锁 | ✓ | ✗ |
| `zeromq` | ✗ tcp 下发布端 bind，端口独占 | ✓ | ✓ 发送端加锁 | ✓ | ✓ |
| `nng` | ✗ tcp 下发布端 listen，端口独占 | ✓ | ✓ 发送端加锁 | ✓ | ✓ |
| `websocket` | ✗ 端口独占 acceptor | ✓ | ⚠ 加锁，但写失败会自锁 | ✓ | ⚠ 同多线程写 |
| `rabbitmq` | ✓ broker 汇聚 | ✓ 每订阅独立队列 | ✓ 连接加锁 | ✓ 每订阅独立连接与线程 | ✓ |
| `redis` | ✓ | ✓ `PSUBSCRIBE` | ✓ 两种 sender 模式均安全 | ⚠ add/remove 竞争 | ✓ |
| `nats` | ✓ | ✓ | ✓ 发送端加锁 | ⚠ add/remove 竞争 | ✓ |

图例：✓ 支持；✗ 不支持或不安全；⚠ 可用但有已知风险。"多进程读"都是扇出语义：每个读进程各收一份。

## 默认并发特性与所需选项

下表回答"默认配置下能不能这样用；不能的话要加什么"。"选项"指 locator 的 `[...]` 属性或调用参数。没有选项可用的，给出推荐的使用方式。

### 广播：多线程写（同进程多个线程调同一 publisher）

| 传输 | 默认 | 需要的选项 / 做法 |
|---|---|---|
| `shm_seqlock` | ✗ 撕裂数据，读端无法检测（实测约 15–25% 消息损坏） | **所有**指向该段的 locator（含心跳）加 `writerLock=true`；或心跳走独立段 |
| `shm_cursor` | ✗ 撕裂数据（实测约 5–9%） | **所有** locator 加 `publisherLock=true`；或心跳走独立段 |
| `aeron_ipc` | ✗ 共享 log buffer 被写坏，所有读者受影响 | 无选项。图内用 `oneBroadcastPublisher(..., threaded=true)`；心跳/告警走独立 stream，或在 `aeron_ipc_getPublisher` 返回的函数外自加 mutex |
| `shared_memory_broadcast` | ✓ `publish` 全程持跨进程 `listMutex`，多写者被串行化。早期实测的 SIGSEGV 来自读者切换链尾的竞争，tm_transport `ccb9a8c` 已修复（修复前的版本仍按 ✗ 处理） | 不需要；多个写线程会在 `listMutex` 上互相等待 |
| `singlecast` | ✗ Asio socket 无锁共享 | 无选项。外部串行化，心跳走独立 locator |
| `multicast` / `zeromq` / `nng` / `rabbitmq` / `redis` / `nats` | ✓ 发送端加锁 | 不需要 |
| `websocket` | ⚠ 加锁，但客户端断开时会自锁 | 无选项。避免多线程同时发布，或在客户端断开不频繁的场景使用 |

### 广播：多线程读（同进程多个订阅 client）

所有广播传输默认都支持：每个信道（段 / locator / topic）一条读线程，该信道上所有 client 的回调在这条线程上**串行**执行。要求：

- 回调里**不要同步** `addSubscriptionClient` / `removeSubscriptionClient`，会死锁；放到新线程做。
- 回调不要长时间阻塞。对 `aeron_ipc` 尤其重要，见下文"aeron_ipc 慢读者"。
- 运行期频繁增删订阅时，`redis` / `nats` 有 add/remove 的 use-after-free 窗口；建议启动期一次性建好订阅。

### 广播：多进程写（多个进程往同一信道发）

| 传输 | 默认 | 说明 |
|---|---|---|
| `shm_seqlock` / `shm_cursor` | ✗ 第二个进程被 `flock` 拒绝并抛异常 | 设计如此，无选项。需要多个发布者时每个进程用独立段 |
| `aeron_ipc` | ✓ 每进程一个 session | 读者按 session 分别处理；不同发布者之间无顺序保证 |
| `shared_memory_broadcast` | ⚠ 段不排他，压测中未观察到问题，但发布路径与清理逻辑未按多写者设计验证 | 不建议；每个进程用独立段 |
| `multicast` / `singlecast` | ✓ | 跨发送者无序 |
| `zeromq` / `nng`（tcp） / `websocket` | ✗ 发布端 bind/listen，端口独占 | 无选项。改用 broker 类传输，或每进程独立端口 |
| `rabbitmq` / `redis` / `nats` | ✓ broker 汇聚 | 不需要 |

### 广播：多进程读

除 `singlecast`（端口只能一个读进程 bind）外默认都支持，每个读进程各收一份。四种 IPC 传输均实测通过（1 发布进程 + 3 订阅进程）。

### Facility

| 需求 | 支持的传输 | 不要用 |
|---|---|---|
| 多 server 进程负载均衡 | `rabbitmq`（共享队列，天然轮询） | `redis` / `nats`：每个 server 都处理每个请求；`socket_rpc` / `json_rest` / `websocket`：端口独占；`grpc_interop`：可能被 `SO_REUSEPORT` 静默分流 |
| client 多线程调用 | `rabbitmq`、`redis`、`grpc_interop`、`json_rest` | `nats`（首次请求竞争）、`websocket`（请求丢失风险）；`socket_rpc` 帧不交错但断线后不重连 |
| server 跨线程回复 | 全部可以 | `websocket` 写失败时自锁 |

### 通用：图内多上游与心跳

- **图内多个上游连到同一个 sink**：调用 `oneBroadcastPublisher(..., threaded=true)`。这是所有"无锁"传输在图内的标准解法。
- **心跳 / 告警与数据共用 locator**：`threaded=true` 管不到。对 `shm_seqlock` / `shm_cursor` 在所有 locator 上加锁属性；对 `aeron_ipc` / `singlecast` 让心跳走独立信道（`shared_memory_broadcast` 自 `ccb9a8c` 起可以共用）。

### 所有广播组件共有的两点

- **回调持锁执行**。订阅回调在持有该订阅（或组件）互斥量时调用，互斥量不可重入。**在回调里同步调 `addSubscriptionClient` / `removeSubscriptionClient` 会死锁**。各 `fetchFirstUpdateAndDisconnect` 都把 remove 放到新线程里做，自写代码照此处理。
- **add 与"最后一个 remove"并发**。多数组件在 `addSubscriptionClient` 里先在锁内拿到订阅对象的裸指针、释放锁，再调 `addSubscription`；同一时刻另一线程移除该订阅的最后一个客户端会把对象销毁。属潜在 use-after-free。在启动期一次性建好订阅、运行期不增删即可避开。

## Facility 传输并发矩阵

| 传输 | 多 server 进程同一信道 | 多 client 进程 | client 多线程调用 | server 跨线程回复 |
|---|---|---|---|---|
| `rabbitmq` | ✓ 轮询负载均衡，不重复 | ✓ | ✓ | ✓ |
| `redis` | ✗ 每个 server 都收到并处理每个请求 | ✓ | ✓ | ✓ |
| `nats` | ✗ 同 redis（未用 queue group） | ✓ | ✗ 首次请求与 remove 有竞争 | ✓ |
| `socket_rpc` | ✗ 端口独占 | ✓ | ⚠ 帧不交错；同 host:port 只能一个 client | ✓ 串行 |
| `grpc_interop` | ⚠ gRPC 默认 `SO_REUSEPORT`，可能被内核静默分流 | ✓ | ✓ | ✓ |
| `json_rest` | ✗ 端口独占 | ✓ | ✓ | ✓ |
| `websocket` | ✗ 端口独占 | ✓ | ⚠ 有请求丢失与悬垂指针风险 | ⚠ 写失败会自锁 |

## 同机 IPC 传输

### shm_seqlock

- **多进程写**：发布者对 `/dev/shm/<段名>.lock` 取 `LOCK_EX|LOCK_NB`，失败即抛 "another live publisher holds ..."（`tm_transport/src/shm_seqlock/ShmSeqlockComponent.cpp:307`）。
- **多线程写，默认 `writerLock=false`**：`publish()` 里的 `next_`、`lastTopic_`（`std::string`）、`lastTopicHash_` 都没有同步（`ShmSeqlockComponent.cpp:452`）。并发调用的后果：
  - 两个线程拿到同一个 `next_`，写同一个 slot。一个线程的偶数提交 seq 让读者认为 slot 已完成，另一个线程还在 memcpy，读者拿到**通过 seqlock 校验的撕裂数据**，无法检测。
  - `lastTopic_ = topic` 并发赋值是 `std::string` 数据竞争（UB，可能堆损坏）；`topicHash` 可能与 topic 不匹配，读端按 hash 过滤时消息被分错或丢掉。
- **`writerLock=true`**：主路径由 `atomic_flag` 自旋锁保护（`:461`、`:539`），可安全多线程写（实测 4 线程无损坏）。锁外的 futex 唤醒段计数 `emptyWakes_` / `waiterResets_` 和 `reject()` 的 `rejected_` 已改为原子 RMW（`:246`–`:252`、`:546`–`:552`），不再丢计数。持锁线程被抢占时其他发布线程空转，会拉高尾延迟。
- **多线程读**：每段每个组件一条读线程，回调串行。读端属性由该段第一个订阅决定。

### shm_cursor

- **多进程写**：独占 `flock`，重试约 2 秒后抛错（`tm_transport/src/shm_cursor/ShmCursorComponent.cpp:250`）。
- **多线程写，默认 `publisherLock=false`**：`next_++` 不是原子操作（`:381`）。
  - 两线程拿到同一个 `i`，写同一个 slot。
  - 拿到不同 `i` 也不行：A 写 slot i、B 写 slot i+1，B 先 `commit.store(i+1)`，读者就去读 A 还在写的 slot。读端的覆盖检测只看 `claim >= j + slotCount`（`:711`），这种情况检测不到，会交付撕裂数据。`commit` 还可能倒退。
- **`publisherLock=true`**：锁覆盖 claim、写数据、commit 和 futex 唤醒（`:375`），`reject` 用 `fetch_add`（`:213`），可安全多线程写。
- **多线程读**：每段一条读线程；客户端集合在 `clientsMutex_` 下更新，读线程靠 `version_` 感知变化，热路径不取锁（`:439`–`:443`）。

### seqlock / cursor 的配置陷阱：第一个 locator 决定属性

两者的 sender 都**只按 identifier（段名）**复用，属性（包括 `writerLock` / `publisherLock`）由本进程里第一个用到该段的 locator 决定（seqlock `ShmSeqlockComponent.cpp:1135`，cursor `ShmCursorComponent.cpp:1044`）。心跳通常在建图之前初始化：如果只在 exporter 的 channel spec 里写了锁属性、心跳 locator 没写，实际生效的是**无锁版本**，没有任何报错。要么给所有指向该段的 locator 都加锁属性，要么让心跳走独立的段。

### aeron_ipc

- **多进程写**：没有 `flock`。每个发布进程是 Aeron 的一个独立 session，读者按 session 区分并处理 `joinLatest`（`tm_transport/src/aeron_ipc/AeronIpcComponent.cpp:656`–`:702`）。可以多进程写，但不同发布者之间**没有顺序保证**，读者可能看到交错。
- **多线程写：不支持，也没有开关**。底层是 `aeron_exclusive_publication_try_claim`（`:481`），Exclusive publication 规定单线程使用（头文件说明 `tm_transport/tm_kit/transport/aeron_ipc/AeronIpcComponent.hpp:75`）。并发 claim 时 term offset 的推进不是原子的，两个 claim 可能重叠、帧头互相覆盖，损坏的是**共享 log buffer**，影响所有读者（malformed、读者卡在异常帧长、image 失效），比丢一条消息严重得多。
- **共享规则**：`publishers_` 以完整 `ConnectionLocator` 为 key（`:1029`、`:1057`），`operator==` 比较包括属性在内的全部字段（`tm_transport/src/ConnectionLocator.cpp:188`）。心跳与 exporter 的 locator 完全相同时共用一个 exclusive publication，发生上述竞争；属性不同时会在同一个 stream 上再建一个 publication（另一个 session），则不冲突。
- **规避**：心跳走独立 stream；或在 `aeron_ipc_getPublisher` 返回的函数外自行加 mutex；或给组件增加改用 `aeron_publication_t`（线程安全，claim 多一次 CAS）的选项（当前代码未提供）。
- **多线程读**：每 locator 一条轮询线程，回调在该线程执行，`kFragmentLimit=64`（`:536`）。

#### aeron_ipc 慢读者（untethered，默认 `tether=false`）

- **现象（修复前，实测）**：同一 stream 上有多个读者（例如多个组件）时，若某读者的回调停顿超过 `untetheredWindowLimitTimeoutMs + untetheredLingerTimeoutMs`，driver 把它移出流控，publisher 随快读者往前写并清零、复用该读者正在读的 term。fragment handler 拿到的是指向共享 term buffer 的零拷贝指针，回调期间数据被改写，client 收到坏数据，`malformed` 仍为 0。单读者时不会触发（LINGER 状态仍参与 `min_sub_pos`）；`tether=true` 不受影响。
- **修复后行为**：
  1. 默认超时：`05962f6` 曾从 10ms / 10ms 调到 2000ms / 2000ms，但慢读者在被踢出前会一直反压 publisher，`backPressure=drop` 下这段时间**所有读者**（包括快读者）都丢消息（aeron_ipc_test 的 test3 因此失败）。tm_transport `8bb9d5c` 已改回 **10ms / 10ms**（`:426`–`:427`），正确性由下面第 2 点保证。需要更长保护期时用 locator 属性 `untetheredWindowLimitTimeoutMs` / `untetheredLingerTimeoutMs` 调大，代价是慢读者拖累全体。
  2. `handleFragment()` 先快照帧头，把整帧拷到轮询线程私有的缓冲区，再复核帧头（`:656`–`:702`）；不一致说明 term 已被清零或轮转，丢弃该帧并计入 `AeronIpcSubscriberStats::overrun`（`AeronIpcComponent.hpp:93`）。client 回调只读本地拷贝。
  3. 代价：每条消息多一次 memcpy。256B payload 下 p50 约 +7%–14%（+35–60ns），p99 约 +2%–3%（每组 2 个有效样本）。
- **仍需注意**：回调停顿超过保护期后再加上 Aeron 客户端的 `aeron.client.resource.linger.duration`（默认 3s），log buffer 可能被释放（上游 [aeron#1675](https://github.com/aeron-io/aeron/issues/1675)）。不要在订阅回调里做长时间阻塞的工作；需要慢处理时在回调里拷贝后转交其他线程。
- **选项**：需要"慢读者绝不丢数据、可以拖住发布者"时用 `tether=true`（配合 `backPressure=retry` 时发布端会被阻塞）。

### shared_memory_broadcast

基于 Boost.Interprocess，`open_or_create` 打开段，没有排他机制（`tm_transport/src/shared_memory_broadcast/SharedMemoryBroadcastComponent.cpp:519`）。每个订阅者登记一条记录和自己的队列，发布者把消息复制到每个活跃订阅者的队列尾部，用 CAS 追加。sender 按 identifier 复用（`:712`）。

- **多读者组件（已修复，实测）**：修复前 `publish()` 无锁遍历订阅者链表，订阅者析构并发 `destroy_ptr` 节点，发布端 SIGSEGV（单写者、3 组件 × 3 client 即可复现）。现在头节点 `SharedMemoryBroadcastClientListItem` 内有进程间互斥量 `listMutex`（`:55`），`publish()` 遍历期间（`:544`–`:548`）、订阅者析构释放节点之前（`:359`）以及读线程切换链尾时（`swapTail()`，`:148`）都持有它。
  - **布局变更**：头节点结构变了，新旧二进制不能共用同一个段；升级前删除 `/dev/shm/` 下的旧段。
  - 订阅 churn 期间可能出现少量重复 / 乱序（新订阅者会收到注册前瞬间的消息），属于设计特性。
- **读者切换链尾的竞争（已修复，实测）**：读线程原先无锁切换 tail 后立即释放旧链，发布者可能还在对旧链尾节点做 CAS，导致 SIGSEGV 或消息挂在已释放节点上丢失（单发布线程也能复现）。`ccb9a8c` 起 `swapTail()` 在 `listMutex` 下进行，共享内存布局不变。`ipc_concurrency_test` 的 4 写者图用例修复前 12 次中 3 次 SIGSEGV，修复后 30/30 全收齐。
- **多线程写（`ccb9a8c` 起支持，实测）**：`publish()` 全程持有 `listMutex`，多写者本就被串行化；早期结论"4 线程无锁并发写 SIGSEGV / 挂起"的原因是上一条的读者竞争，而不是分配器并发。修复后 `ipc_concurrency_test` 中 shared_memory_broadcast 的多写用例全部通过。旧版本仍需图内 `threaded=true` 或外部加 mutex。
- **多进程写**：段不排他，压测中未观察到问题，但发布路径与失效订阅者清理没有按多写者验证，不建议。
- **取消订阅（已修复）**：读线程原先被 `detach`，析构里对它 `join` 必然抛异常被吞掉，随后立刻释放读线程仍在使用的共享内存，取消订阅时可稳定复现 SIGSEGV。现在析构先 join 读线程再释放（`:341`–`:353`，阻塞等待模式最长约 1 秒；从自身回调里析构时退化为 detach），订阅销毁移到组件锁之外。
- 其他潜在风险（读代码得出，未实测）：唤醒用进程内互斥量，`notify_one` 不持锁，可能丢唤醒，最多多等约 1 秒。

## 网络广播传输

### multicast

- **多进程写**：发送端设 `reuse_address`，多进程可同时发；跨发送者无序。超过 1200 字节的负载被静默丢弃。
- **多进程读**：订阅端 `reuse_address(true)` 后 bind `0.0.0.0:port` 并 join 组（`tm_transport/src/multicast/MulticastComponent.cpp:192`–`:195`），每进程各收一份。由于绑定 `0.0.0.0:port`，Linux 上同端口的其他组也会被收到（`IP_MULTICAST_ALL` 默认开），`ignoreTopic` / Binary 编码下没有 topic 过滤兜底。loopback 保持系统默认（开），同机发送者会收到自己的消息。
- **多线程写**：`set_option(hops)` 和 `async_send_to` 都在发送端 `mutex_` 内（`:590`–`:602`），安全。sender 按 `{host,port}` 复用（`:712`）。
- **数据与心跳共用 locator**：安全，但 exporter 默认 `ttl=0`、心跳 `ttl=1`，交替发布时每次切换都会多一次 `setsockopt`；`ttl=0` 也意味着数据不出本机，需要跨机时在 locator 上写明 `ttl`。
- 启用 `MULTICAST_COMPONENT_SENDER_USE_ZERO_COPY_BUFFER` 时，缓冲池（1024 块）耗尽会返回空指针并被解引用，多线程突发流量下可能崩溃。

### singlecast

- **多进程写**：发送 socket 不 bind，各进程用临时端口，可以多进程发；跨发送者无序；超过 1200 字节静默丢弃。
- **多进程读：不支持**。订阅端 bind `0.0.0.0:port` 且没有 `reuse_address`（`tm_transport/src/singlecast/SinglecastComponent.cpp:177`–`:184`），第二个进程 bind 失败抛异常。订阅按 `{host,port}` 区分（`:382`），但实际都绑 `0.0.0.0`，同端口不同 host 的两个 locator 在同一进程里也会 bind 失败。
- **多线程写：不安全**。`publish` 不加锁，多个线程直接在同一个 socket 上调 `async_send_to`（`:319`–`:345`），同时 sender 自己的 io 线程在跑完成回调；Asio socket 对象不支持这种共享。sender 按 `{host,port}` 复用（`:476`），心跳与 exporter 共用 locator 时就会出现这种情况。
- 订阅析构 `close()` socket 后读线程的 `run()` 随即返回：`ccb9a8c` 起读线程不再持 work guard，`io_context` 由订阅与读线程通过 `shared_ptr` 共同持有，不再每次订阅/退订泄漏一条线程。

### zeromq

- **多进程写**：tcp 模式下发布端固定 `bind("tcp://*:"+port)`，忽略 locator 的 host（`tm_transport/src/zeromq/ZeroMQComponent.cpp:289`、`:297`），第二个进程 bind 同一端口抛 `zmq::error_t`。PUB 只能有一个进程。
- **多进程读**：每个订阅者 connect 并 subscribe 空前缀，在客户端过滤 topic。
- **多线程写**：`publish` 整体在 `mutex_` 内，包括序列化与 `send`（`:305`–`:316`）；这把锁也提供了 libzmq 在线程间移交 socket 所需的内存屏障。sender 按 `(host,port,identifier)` 复用（`:366`），心跳与 exporter 共用一个 socket，不会重复 bind。`send` 用 `dontwait`，到达 HWM 后**静默丢消息**。
- 超过 16 MB 的消息被丢弃。`inproc` 要求发布与订阅在同一个组件内（共享 `ctx_`）。

### nng

- **多进程写**：tcp 模式 `listen("tcp://*:"+port)`（`tm_transport/src/nng/NNGComponent.cpp:257`–`:259`），端口独占；只支持 `ipc` 和 `tcp`。
- **多进程读**：每个订阅者独立 dial。潜在风险（未实测）：连续约 10 秒收不到消息后，代码会在同一个 socket 上再次 dial，而 nng dialer 本身会自动重连，可能形成重复 pipe、收到重复消息。
- **多线程写**：序列化在锁外，`send` 在 `mutex_` 内（`:267`–`:276`），安全；`nonblock` 发送，可能丢消息。sender 按 locator 复用（`:321`）。
- 析构里显式调 `sock_.~socket()`（`:264`），之后成员析构会再关一次。

### websocket（广播）

- **多进程写**：服务端 acceptor bind `0.0.0.0:port`，`reuse_address` 在 Linux 上不允许两个进程同时监听，第二个抛异常。同一进程内按端口复用 publisher，identifier 作为 path，一个端口可承载多个 path。
- **多进程读**：每个订阅者一条独立连接。
- **多线程写**：`publish` 持 `clientHandlersMutex_`（`tm_transport/src/websocket/WebSocketComponent.cpp:1229`），每个客户端在 `writeMutex_` 下做**同步阻塞写**（`:1133`–`:1141`），在调用线程上执行。正常情况下线程安全，但：
  - **写失败会自锁**：写抛异常时 catch 里调 `removeClientHandler`（`:1145`），后者再次锁 `clientHandlersMutex_`（`:1292`），`std::mutex` 不可重入，死锁（严格说是 UB），还会修改正在遍历的集合。触发条件只是**发布过程中有任一客户端断开**。reactor 回复路径（约 `:1078`）是同一模式，未逐行核实。
  - 慢客户端会阻塞该端口上所有发布线程。
  - `finalizeEnvironment` 之前发布的消息被丢弃。
- **多线程读**：每个订阅一条 io 线程（或 `useIXWebSocket=true` 时的 IXWebSocket 线程），回调在 `clientsMutex_` 下串行执行。

## Broker 广播传输

### rabbitmq

- **多进程写 / 读**：由 broker 的 topic exchange 汇聚和扇出；每个订阅者有自己的服务器命名队列。
- **多线程写**：每个 locator 一条发布连接，`OnePublishingConnection::mutex_` 同时覆盖 publish 与 `amqp_get_rpc_reply`（`tm_transport/src/rabbitmq/RabbitMQComponent.cpp:244`–`:262`）。librabbitmq 不是线程安全的，这把锁是必需的。心跳、exporter、facility 流量都共用这条连接，被锁串行。
- **多线程读**：每个订阅独立连接和读线程，回调在该线程执行，不持锁。
- 风险：
  - 一次失败的 publish（例如 exchange 不存在）会关闭共享的 channel 1，同连接上所有发布者都受影响，而 publish 返回值未检查，无法可靠发现。
  - 订阅队列非 exclusive、非 auto-delete，可能在进程退出后残留；消息 1 秒过期。
  - 默认 `ExceptionPolicy::Throw` 在读线程里重新抛出会导致 `std::terminate`。
  - 在自己的回调里 remove 订阅会尝试 join 自身线程，之后连接在使用中被销毁（UB）。

### redis

- **多进程写 / 读**：`PUBLISH` / `PSUBSCRIBE`，topic 是 glob；at-most-once，无持久化。
- **多线程写**：两种 sender 模式（`TM_REDIS_SENDER_MODE`）都避免了跨线程共享 `redisContext`：
  - async（默认）：MPMC 队列 + 单个发送线程独占 ctx。队列实际无界；发送失败的批次被丢弃；发送线程里反复出错会抛异常导致 `std::terminate`；退出时队列中未发出的消息丢失，除非设 `TM_REDIS_DRAIN_QUEUE_ON_SHUTDOWN=1`。顺序只在单个生产线程内保证。
  - sync：每个（线程，sender）一个 `thread_local` ctx。进程内 sender 计数只增不减，第 9 个 sender 抛异常；每个新线程都会新开连接。
- sender 只按 `host:port` 复用（`tm_transport/src/redis/RedisComponent.cpp:1235`–`:1240`），用户名、密码、identifier 不参与，**第一个 locator 的凭据生效**。
- **多线程读**：每个 `(host:port, topic)` 一个订阅对象和线程，所有客户端共享；回调在 `mutex_` 下执行。add/remove 之间有前文所述的 use-after-free 窗口。重连后会重新订阅，但断线期间的消息丢失。

### nats

- **多进程写 / 读**：core NATS，at-most-once；普通 `Subscribe`，支持 `*` / `>` 通配。
- **多线程写**：`OneNATSSender::mutex_` 包住 publish（`natsConnection` 本身线程安全，锁只是额外串行化）。sender 按 `host:port` 复用，凭据不参与。
- **多线程读**：每个 `(host:port, topic)` 一条连接和订阅，所有客户端共享，回调在 cnats 投递线程上串行执行。
- 风险：
  - `natsConnection_Connect` / `natsConnection_Subscribe` 返回值从不检查（`tm_transport/src/nats/NATSComponent.cpp:114`–`:116`），连接失败时之后所有发布都静默失败。
  - sender 析构不 flush，缓冲中的消息可能丢失。
  - `~NATSComponent` 在 1 秒后从 detached 线程调用全局 `nats_CloseAndWait`，会破坏同进程中其他仍存活的 `NATSComponent`。

## Facility 传输

### rabbitmq

- **多 server 进程**：server 声明命名共享队列（`RabbitMQComponent.cpp:590`–`:598`），broker 把每个请求只投给一个消费者，**天然轮询负载均衡、不重复**。注意 server 在处理前就 ack（`:538`），是 at-most-once，server 崩溃会丢请求；prefetch 不限，是简单轮询而不是公平分发，慢 server 也照样分到份额。请求 5 秒过期，无人消费时请求丢弃，client 永远等不到回复。
- **client**：每个 client 进程有自己的回复队列，按 correlation id 匹配；多线程调用安全（map 在 `clientsMutex_` 下更新，publish 走加锁的连接）。
- **server 回复**：任意线程安全。

### redis

- **多 server 进程：不安全**。server 用普通 `SUBSCRIBE`（`RedisComponent.cpp:1145`），每个 server 都收到并处理**每一个**请求，各自回复。client 只保留第一个 final 回复，但来自不同 server 的非 final 回复会交错。不要对同一 facility topic 启动多个 server 进程。
- **client**：多进程、多线程都安全。没有请求超时，没有 server 订阅时请求丢失且永远等待。
- 风险：client 与 server 的读线程都被 `detach`（server 见 `:1148`），client 退订时在读线程仍可能使用的 `redisContext` 上发命令（数据竞争）；server 析构对已 detach 的线程 join（异常被吞），随后释放 ctx。server 读线程遇 EOF 直接退出、不重连，facility 会静默停止。

### nats

- **多 server 进程：不安全**。server 用普通 `Subscribe` 而不是 `QueueSubscribe`（`NATSComponent.cpp:440`），效果同 redis：请求被重复处理，没有负载均衡。
- **client 多线程调用：不安全**。回复订阅在锁外懒创建，两个线程同时发首个请求可能对同一个 inbox 订阅两次，泄漏一个订阅，用户回调触发两次；`removeClient` 之后 `clients_[clientNumber]` 用 `operator[]` 会插入空指针并被解引用。
- **server**：回调在单个 cnats 订阅线程上串行执行；回复可从任意线程发出。

### socket_rpc

- **多 server 进程**：acceptor 无 `reuse_address`（`tm_transport/src/socket_rpc/SocketRPCComponent.cpp:430`–`:434`），端口独占。
- **client 多线程调用**：`sendRequest` 在 `mutex_` 下连续两次同步写长度和正文（`:219`–`:235`），帧不会交错。但：
  - `good_` 是普通 `bool`，由 io 线程写、调用线程读，是数据竞争；未连上时请求被**静默丢弃**。
  - **断线重连实际不工作**：重连用的 `deadline_timer` 是局部变量（`:55`），离开作用域即析构并取消等待，回调收到 `operation_aborted`，而 `handleReconnectTimeout` 只在 `!ec` 时重连（`:35`）。server 未先启动或断线一次后，client 不会再连上。
  - client 按 `(host,port)` 唯一（`:524`），同一进程对同一地址建第二个 client 抛 "Cannot create duplicate RPC client"；`typedOneShotRemoteCall` 每次都新建 client，对同一 locator 并发 one-shot 调用会抛异常。
- **server**：整个组件一条 io 线程，请求回调在该线程执行；回复在 server 锁下同步阻塞写，可从任意线程调用，但同端口所有连接的回复串行，一个慢 client 会拖住全部。回复按请求 id 找连接，不同 client 使用相同 id 时会互相覆盖、回复发错对象。

### grpc_interop

- **多 server 进程**：绑定 `[::]:port`。gRPC 在 Linux 上默认开启 `SO_REUSEPORT`（库行为，代码中不可见，未实测），多进程可能**静默地同时绑定同一端口**并由内核分流请求；代码未设置 `GRPC_ARG_ALLOW_REUSEPORT=0`。`BuildAndStart()` 的返回值未判空（`tm_transport/src/grpc_interop/GrpcInteropComponent.cpp:288`、`:298`），绑定失败会在 detached 线程里解引用空指针。
- **client 多线程调用**：client facility 是 `ThreadedHandler`，默认在专用线程串行处理；SharedPool 保留单节点回调串行，Moodycamel 不保证跨生产者全局 FIFO，显式 Inline 则可能并发进入；channel 按 `host:port` 共享（`grpc::Channel` 线程安全）。安全。
- **server**：gRPC callback API，内部线程池并发处理；回复经 reactor 自身锁 + 队列串行 `StartWrite`，任意线程回复安全。
- 陷阱：`finalizeEnvironment` 之后往已有端口注册新 service 不会生效，也不报错；同一 locator 第二次 `setRPCClient` 复用第一个 sender 及其回调，新回调被忽略。

### json_rest

- **多 server 进程**：`reuse_address(true)` 后 bind（`tm_transport/src/json_rest/JsonRESTComponent.cpp:1473`–`:1479`），Linux 上不允许两个进程同时监听，第二个抛 "Cannot bind"。
- **client 多线程调用**：client facility 是 `ThreadedHandler`。默认每个请求一个独立 client 对象和 strand，安全，所有 client 共用一条 io 线程。
  - `use_keep_alive_client=true`：每 `host:port` 一条连接，请求逐个串行；io 线程上的同步写会阻塞所有 client；回调在持有 `requestsMutex_` 时执行，下游在同一线程同步再向同一 host 发请求会重入死锁。
  - `use_curlpp=true`：全局互斥量下在调用线程阻塞执行，完全串行。
- **server**：每端口一条 accept 线程，每连接一个 strand；回复可从任意线程发出。每个请求处理完即关闭连接，不支持 keep-alive。

### websocket（facility）

- **多 server 进程**：端口独占；一个端口上每个 path 只能注册一个 server。
- **server**：每端口一条 io 线程，请求处理串行；`sendReply` 可在任意线程调用，但同样是"持 `clientHandlersMutex_` + 同步写"，写失败时与广播一样**自锁**（约 `:1920`，同一模式，未逐行核实）。请求 id 到连接的映射按 path 而不是按连接，不同 client 的相同 id 会互相覆盖。
- **client 多线程调用**：请求在 `writeMutex_` 下同步写，同 locator 的 facility 共用一条连接，回复按 id 匹配。风险：连接就绪前请求会进缓冲，存在一个窗口让请求在 io 线程清空缓冲后才入队，从此不再发送；连接出错后连接对象被删除，但已返回的发送函数仍持有裸指针（潜在 use-after-free）。

## 实时 / 回测行为差异

| 维度 | RealTimeApp | SinglePassIterationApp / TopDownSinglePassIterationApp |
|---|---|---|
| exporter 调用线程 | 上游节点的线程，多上游即多线程 | 单线程，不存在并发调用 |
| 心跳 | 时钟 importer 线程，与数据线程并发 | 回测通常不挂心跳 |
| 本文风险 | 全部适用 | 不适用：回测里一般不使用这些传输组件，改用文件或合成 importer |

## 易错点

**1. 心跳和数据共用 shm_seqlock / shm_cursor / aeron_ipc / singlecast 信道**

最常见、最隐蔽的一种组合：两个线程无锁写同一个 sender，读端可能静默拿到撕裂数据（shm 类、singlecast），或共享 log buffer 被写坏（aeron_ipc）。心跳改用独立信道最省事。

**2. 只在 exporter 的 locator 上写锁属性**

seqlock / cursor 的锁属性由第一个打开该段的 locator 决定，心跳一般先初始化，详见上文"第一个 locator 决定属性"。

**3. 以为 `threaded=true` 能解决全部并发**

它只串行化图内经过该 sink 的数据，不影响直接调用组件 publisher 的心跳、告警和自写代码。

**4. 在订阅回调里增删订阅**

所有广播组件都会死锁。放到新线程里执行。

**5. 对 redis / nats facility 横向扩容**

多起一个 server 进程不会分摊负载，只会让每个请求被处理两次。需要负载均衡时用 rabbitmq facility。

## 相关章节

- [tm_transport 概览](00-overview.md) — 能力矩阵
- [广播：listener 与 publisher](01-broadcast.md) — `oneBroadcastPublisher` 的 `threaded` 参数
- [远程设施](02-facilities.md)
- [心跳与告警](05-heartbeat-and-alert.md)
- 各传输：[shm_seqlock](03-transports/shm_seqlock.md) · [shm_cursor](03-transports/shm_cursor.md) · [aeron_ipc](03-transports/aeron_ipc.md) · [shared_memory_broadcast](03-transports/shared_memory_broadcast.md) · [multicast](03-transports/multicast.md) · [singlecast](03-transports/singlecast.md) · [zeromq](03-transports/zeromq.md) · [nng](03-transports/nng.md) · [websocket](03-transports/websocket.md) · [rabbitmq](03-transports/rabbitmq.md) · [redis](03-transports/redis.md) · [nats](03-transports/nats.md) · [socket_rpc](03-transports/socket_rpc.md) · [grpc_interop](03-transports/grpc_interop.md) · [json_rest](03-transports/json_rest.md)
