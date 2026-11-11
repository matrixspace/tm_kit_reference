---
title: 实时 handler 与可替换执行器
library: tm_infra
headers: [tm_kit/infra/RealTimeThreadedExecutor.hpp, tm_kit/infra/RealTimeApp.hpp, tm_kit/basic/RealTimeSharedPoolExecutor.hpp, tm_kit/basic/MoodycamelThreadedExecutor.hpp, tm_kit/basic/RealTimeMPSCQueue.hpp, tm_kit/basic/HwlocThreadCpuAllocator.hpp]
keywords: [ThreadedHandler, ExecHandler, HandlerPolicy, ThreadedPolicy, InlinePolicy, InlineExecutor, DedicatedThreadExecutor, RealTimeThreadedExecutorComponent, RealTimeThreadedExecutorFor, RealTimeSharedPoolExecutor, RealTimeSharedPoolExecutorComponent, SharedThreadPool, SharedThreadPoolConfig, MoodycamelThreadedExecutor, MoodycamelThreadedExecutorComponent, ThreadedExecOptions, ThreadedNodeOptions, configureThreadedNode, configureThread, spinWait, 绑核, Cpus, CpuAutoBind, CpuAutoBindOnNuma, HwlocThreadCpuAllocator, HwlocThreadCpuAllocatorComponent, HwlocCrossProcessCpuAllocatorComponent, CpuAllocatorScope, crossProcessLockDir, reserveReplacing, 多进程协商, flock, HwlocCpuAllocatorConfig, ThreadCpuLease, SmtPolicy, hwloc, NUMA, kOwnContext, kSerialCallbacks, wakeIdle, threadHandle, 执行器, 线程池, 共享线程池, 同步执行, FIFO顺序, strand, FIFO, concurrentqueue, moodycamel_executor]
---

# 实时 handler 与可替换执行器

## 用途

`RealTimeApp` 把节点逻辑和调度方式分开：统一的 `ExecHandler` 负责数据分派、时间与版本检查，执行器（executor）决定是在调用线程同步处理、专用线程处理，还是交给共享线程池。通过 Environment 选择执行器，无需为 action、exporter、facility 各维护同步与异步两份实现。

本文对应 2026-11-11 的 `develop` 源码（含逐节点 spinWait/绑核与 CpuAutoBind）；具体 commit 见 [VERSIONS.json](../VERSIONS.json)。默认执行器是 **infra 的 mutex/list `DedicatedThreadExecutor`**。早期开发记录中的默认 MPSC、Enhanced 执行器和带 `ThreadedExecMode` 的契约均为历史方案。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/RealTimeThreadedExecutor.hpp>
#include <tm_kit/infra/RealTimeApp.hpp>
// 可选实现，属于 tm_basic：
#include <tm_kit/basic/RealTimeSharedPoolExecutor.hpp>
#include <tm_kit/basic/MoodycamelThreadedExecutor.hpp>
```

契约、Inline、默认 Dedicated 在 `dev::cd606::tm::infra`；SharedPool、Moodycamel 在 `dev::cd606::tm::basic`。`basic/RealTimeMPSCQueue.hpp` 为 SharedPool 提供侵入式 MPSC 队列，infra 不再安装该队列或共享池头文件。

## 核心类型与签名

### handler 如何选择执行器

`RealTimeAppComponents<StateT>` 的公开策略定义在 `tm_infra/tm_kit/infra/RealTimeApp.hpp:225`：

```cpp
struct ThreadedPolicy {
    template <class Item>
    using Executor = RealTimeThreadedExecutorFor<StateT, Item>;
};
struct InlinePolicy {
    template <class Item>
    using Executor = InlineExecutor<Item>;
};
template <bool Threaded>
using HandlerPolicy = std::conditional_t<Threaded, ThreadedPolicy, InlinePolicy>;
```

框架中基于 handler 的 action / multi-action、facility 和 exporter 采用统一实现。`SuggestThreaded(false)` 选 `InlinePolicy`，`true` 选 `ThreadedPolicy`。`simpleImporter`、`triggerImporter<HasOwnThread>`、`BunchedImporter` 等自行创建线程的节点，以及传输层自身的 IO 线程，不因此改为执行器调度。trigger importer 的 `HasOwnThread` 仍控制其本地线程，与 handler 策略不同。

`RealTimeThreadedExecutorFor<StateT, Item>` 检测 `StateT::template RealTimeThreadedExecutor<Item>`；没有该成员模板时选择 `DedicatedThreadExecutor<Item>`。选择组件的真实声明（`tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp:255`）：

```cpp
template <template <class> class Exec>
struct RealTimeThreadedExecutorComponent {
    template <class Item>
    using RealTimeThreadedExecutor = Exec<Item>;
};
```

因此该组件只改变走 `ThreadedPolicy` 的 handler。若显式选 `RealTimeThreadedExecutorComponent<InlineExecutor>`，原本 threaded 的 handler 也同步执行；`SuggestThreaded(true)` 不能再解释为“一定创建专用线程”。普通非 threaded 节点仍固定走 Inline。

### 契约是 Exec&lt;Item&gt;

`tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp:17` 的契约要求执行器提供：

| 接口 | 含义 |
|---|---|
| `Exec(ThreadedExecOptions)` | 接收框架的执行选项 |
| `kOwnContext` | 回调是否在调用者之外的执行上下文运行 |
| `kSerialCallbacks` | 同一个 host 的回调是否互斥；不保证固定 OS 线程 |
| `start(Host *)` | 安装 host；异步执行器在其他回调前调用一次启动等待 |
| `bool push(Item &&)` | 提交数据；停止后拒收。不是处理完成或持久化确认 |
| `stop()` | 非阻塞，允许在回调内调用；不保证排空待处理数据 |
| `wakeIdle()` | host 的 idle 状态变化后唤醒执行器 |
| `threadHandle()` | 返回 `std::optional<std::thread::native_handle_type>` |
| `bool configure(ThreadedNodeOptions const &)` | **可选**。逐节点 spinWait / 绑核；没有该成员时框架按不支持处理，返回 false 且不报错 |

host 适配器提供 `executorWaitForStart()`、`executorHandle(...)`、`executorIdleWork()`、`executorHasIdleWork()`、`executorBeforeBatch(...)`。Inline 不调用启动等待或 idle 回调。异步执行器的 idle 只在没有待处理数据时运行。

每生产者 FIFO 是基本要求；跨生产者的顺序必须看具体实现。`kSerialCallbacks=false` 时，框架使用保护版 `TimeChecker<true,T>`；为 true 时使用非保护版。见 `tm_infra/tm_kit/infra/RealTimeApp.hpp:288` 和 [时间检查](07-time-and-data.md#时间倒流检查timechecker-与-checktimecomponent)。**时间检查的互斥量不保护业务回调自身的共享状态。**

### 四种实现的差异

| 执行器 | 每节点上下文 | 同一 host 回调串行 | 跨生产者全局 FIFO | `threadHandle()` | 逐节点 spinWait / 绑核 |
|---|---|---|---|---|---|
| `infra::InlineExecutor<Item>` | 无，直接在调用线程执行 | 否，多生产者可并发进入 | 无串行队列 | `nullopt` | 忽略，返回 false |
| `infra::DedicatedThreadExecutor<Item, Config>` | 一条专用线程，默认 | 是 | 保留 mutex 入队线性化顺序 | 原生线程句柄 | 绑核生效；spinWait 忽略；析构 join |
| `basic::RealTimeSharedPoolExecutor<Item>` | 进程共享池，每节点一个 strand | 是，同一节点回调不重叠 | 保留该节点 MPSC 入队线性化顺序 | `nullopt` | 忽略，返回 false（用池级配置） |
| `basic::MoodycamelThreadedExecutor<Item, Config>` | 一条专用线程，可选 | 是 | **不保证**，仅每生产者 FIFO | 原生线程句柄 | spinWait 与绑核均生效；析构 join |

SharedPool 的 strand（串行执行单元）允许节点在不同池线程之间迁移，不能依赖 per-node `thread_local`、固定线程 ID 或逐节点绑核。不同节点仍可并发；两个节点共享业务状态时仍需同步。阻塞 IO、长时间重试或等待启动屏障会占住池线程，应保留专用线程。

### 默认 Dedicated：保留 mutex/list，修复空等

定义见 `tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp:100`。生产者在 mutex 下追加 `std::list<Item>`，消费者把整批 `splice` 到本地处理列表。等待带 predicate：若处理期间又有数据入队，下一轮立即处理，不再无条件白等 1ms。这项修复针对该执行器；未覆盖自带线程的 trigger / bunched / simple importer 的其他等待路径。

`DedicatedThreadExecutorConfig::idlePeriod` 默认 1ms；保持历史周期 idle 行为，即使 `executorHasIdleWork()` 为 false 仍周期回调。默认实现忽略 `ThreadedExecOptions::spinWait`、逐节点 `ThreadedNodeOptions::spinWait` 和 `Config::spinBeforeSleep`，不能用这些字段让默认执行器忙等；逐节点绑核则生效（见下节「逐节点 spinWait 与绑核」）。

### 逐节点 spinWait 与绑核

同一张图里不同节点的实时性要求往往不同：关键路径节点值得多自旋，低频节点应尽快睡下。`ThreadedNodeOptions` 让每个 threaded 节点在**图启动前**单独配置（`tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp:141`）：

```cpp
struct ThreadedNodeOptions {
    std::optional<std::chrono::nanoseconds> spinWait; // 空 = 保持执行器默认
    std::vector<int> cpus;                            // 空 = 保持现有绑核
    std::optional<CpuAutoBindRequest> cpuAutoBind;     // 自动选核，见下节
    ThreadedNodeOptions &SpinWait(std::chrono::nanoseconds);
    ThreadedNodeOptions &Cpus(std::vector<int>);
    ThreadedNodeOptions &CpuAutoBind();               // 全局自动选核
    ThreadedNodeOptions &CpuAutoBindOnNuma(int node); // 限定 NUMA 节点
};
```

调用点在 `RealTimeApp` 的静态函数，和 `threadHandle(node)` 同一形状（`tm_infra/tm_kit/infra/RealTimeApp.hpp:3122`）：

```cpp
M::configureThreadedNode(action, ThreadedNodeOptions()
    .SpinWait(std::chrono::microseconds(100))
    .Cpus({20, 21}));   // 节点创建之后、r.finalize() 之前
```

语义要点：

- **时机**：节点在线构造时线程就已启动，所以这是“设置”，不是“启动参数”。绑核立即作用于已运行的线程；Moodycamel 的 spinWait 从消费者下一次等待起生效。没有要求在运行中动态调整。
- **返回值**：`true` 表示执行器接受了设置。Dedicated 按约定忽略 spinWait 但仍返回 `true`；`false` 表示节点非 threaded（Inline）、执行器不支持（SharedPool、旧的自定义执行器），或 CPU 号无效 / 设置亲和性失败。CPU 号无效时整个调用都不生效，原绑核与 spinWait 保持不变。
- **空 `cpus`** 不会清除已有绑核。要改变绑核，给出非空集合。
- **自旋预算是每节点的**：`ThreadedNodeOptions::spinWait` 覆盖该节点执行器的默认值，互不影响。
- **SharedPool 仍是池级**：它的 `spinWait` 与 `cpus` 在 `SharedThreadPoolConfig` 中配置，节点级调用返回 `false` 且不报错。

扩展点：执行器只要提供 `bool configure(ThreadedNodeOptions const &)` 就自动被框架识别，无需改 `RealTimeApp`；没有该成员的执行器被视为不支持。

### 自动绑核（CpuAutoBind）

手工 `Cpus()` 要求调用者自己理解 taskset/numactl 限制、SMT 兄弟和 NUMA 布局。`CpuAutoBind()` 把这些交给框架：为忙线程（包括 busy-loop 线程）挑一个最优 CPU（`tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp`）。

```cpp
M::configureThreadedNode(node, ThreadedNodeOptions().CpuAutoBind());            // 由框架挑核
M::configureThreadedNode(node, ThreadedNodeOptions().CpuAutoBindOnNuma(1));     // 只在 NUMA 节点 1 内挑
```

参数是 **NUMA 节点，不是 CPU 号**。要固定到具体 CPU 用 `Cpus()`；自动模式只约束“在哪个范围里挑”，具体用哪个核（避开 SMT 兄弟、节点首核、第三方占用的核）由框架决定。`Cpus()` 与 `CpuAutoBind*` 同时给出会抛 `std::invalid_argument`。

**分配规则**

1. 可用 PU = `hwloc_get_cpubind(PROCESS)` ∩ `hwloc_topology_get_allowed_cpuset`，因此 taskset、`numactl --physcpubind/--cpunodebind` 和 cgroup cpuset 都会被遵守。拓扑以 `HWLOC_TOPOLOGY_FLAG_INCLUDE_DISALLOWED` 加载，被掩码禁用的 SMT 兄弟仍留在核里，所以“每核只暴露一个 PU”的 cgroup/taskset 掩码在 `RequireFullCore` 下会被判为没有完整核，而不是误当成整核。
2. 以物理核为单位分配，一个核只给一个忙线程。默认 `SmtPolicy::RequireFullCore` 要求核的所有 PU 都可用；`AllowPartialCore` 放松这一点。
3. 每个 NUMA 节点的**首核**默认避开（`avoidFirstCoreOfNumaNode`）：它承载该节点的中断与内核杂务。
4. `excludeCpus` 是避让列表，按**整个物理核**生效——第三方库在 CPU X 上忙时，X 的 SMT 兄弟也不会被分配。
5. NUMA 选择默认“集中”：先留在已有自动分配、且仍有空闲核的节点；其次是线程 membind 为 BIND 策略时指定的节点；最后按空闲核数排序。`CpuAutoBindOnNuma(n)` 只在节点 n 内挑。
6. 显式 `Cpus()` 在挂了分配器的 Environment 里会被登记为预留，自动分配会避开整核；预留与已自动分配的核冲突时报错，且**按物理核判断**——自动分配了 CPU 2 之后再预留它的 SMT 兄弟 CPU 30 同样报错，隔离保证不依赖配置顺序。预留不可用 CPU 也直接抛异常。两个显式预留落在同一物理核同样报错（同一节点用相同 CPU 重配置除外，见下文 `reserveReplacing`）。
7. `excludeCpus` 所在物理核**任何方式都不能绑定**：自动分配跳过它，显式 `Cpus()`（挂了分配器时）和 `bindCurrentThreadTo` 绑到它（含 SMT 兄弟）抛 `CpuAutoBindError`；列表中任一 CPU 被拒，整次调用不登记任何预留。

**失败一律抛异常**，不静默降级：没有可用核、NUMA 节点不存在或不可用、`excludeCpus` 写了不可用或不存在的 CPU、节点没有专用线程（Inline、SharedPool）等，都会抛出带诊断的异常（列出可用 PU、被排除的核、已分配 CPU 等）。这与 spinWait/`Cpus()` “不支持就返回 false”的约定不同。

**分层**：infra 只提供扩展点，保持零第三方依赖——

```cpp
class IThreadCpuAllocator {             // infra
    virtual int acquire(CpuAutoBindRequest const &, std::string const &who) = 0;
    virtual void reserve(std::vector<int> const &cpus, std::string const &who) = 0;
    virtual void release(std::vector<int> const &cpus) noexcept = 0;
    // 节点重配置：previous 中的 CPU 属于调用者自己，不算冲突。默认实现转调 reserve
    virtual void reserveReplacing(std::vector<int> const &cpus, std::vector<int> const &previous, std::string const &who);
};
template <class Access> struct ThreadCpuAllocatorComponent; // Environment 组件
```

hwloc 实现在 basic（`tm_basic/tm_kit/basic/HwlocThreadCpuAllocator.hpp`，可选）：

```cpp
struct Env : ..., basic::HwlocThreadCpuAllocatorComponent {};

basic::HwlocCpuAllocatorConfig cfg;
cfg.excludeCpus = {8, 9};        // 第三方库已占用的 CPU（整核避让）
basic::HwlocThreadCpuAllocator::configure(cfg);
```

`configure()` 必须在首次使用前调用，之后再调用抛 `std::logic_error`（与 `SharedThreadPool::configure` 相同）。头文件用 `__has_include(<hwloc.h>)` 探测；下游启用该功能需自己链接 hwloc（pkg-config 名 `hwloc`），tm_basic 的 `.pc` 不要求它。未挂载分配器组件就调用 `CpuAutoBind()` 时，节点会抛异常并提示需要的组件。首次加载拓扑失败（例如 `excludeCpus` 含不可用或不存在的 CPU）会整体回滚，不留半成品状态；此时分配器仍算“未使用”，可以再次 `configure()` 修正配置后重试。

### 多进程协商（CrossProcess）

`HwlocThreadCpuAllocatorComponent` 只在本进程内防止忙线程抢同一物理核。同一台机器上多个 tm_kit 进程都用 `CpuAutoBind()` 时，会从相同的候选顺序挑核而撞到一起。把组件换成 `basic::HwlocCrossProcessCpuAllocatorComponent` 即开启跨进程协商（默认关闭）：

```cpp
struct Env : ..., basic::HwlocCrossProcessCpuAllocatorComponent {};

basic::HwlocCpuAllocatorConfig cfg;
cfg.excludeCpus = {8, 9};
// cfg.crossProcessLockDir = "/dev/shm/tm_kit_cpu_locks";   // 默认值
basic::HwlocThreadCpuAllocator::configure(cfg, basic::CpuAllocatorScope::CrossProcess);
```

- **机制**：锁目录（默认 `/dev/shm/tm_kit_cpu_locks`，不存在时以 `01777` 创建）中每个物理核一个 `core-<N>.lock`，N 是该核完整 cpuset 的最小 PU 号，不同 taskset/cgroup 掩码的进程得到同一个键。占用 = 对该文件持有 `flock(LOCK_EX)`；进程以任何方式退出（含 `kill -9`、崩溃）时内核释放锁，没有残留状态需要回收。`lslocks` 可直接看到持有者。
- **覆盖三种绑定方式**：`CpuAutoBind*` 跳过被其他进程占用的核；显式 `Cpus()` 和 `ThreadCpuLease::bindCurrentThreadTo` 碰到其他进程已占的核（含 SMT 兄弟）**一律抛 `CpuAutoBindError`**（独占），消息带锁文件中记录的最后写入者 pid。
- **释放**：线程租约结束或节点析构即释放该核的锁；同一核被多个显式预留引用时按引用计数。
- **excludeCpus 对其他进程也生效**：排除的核由本进程加锁“占住”，其他进程不会分配到；带 scope 的 `configure(cfg, CrossProcess)` 返回前就完成发布，要排除的核已被他人占用时抛异常并回滚配置。
- **NUMA 选择**会计入其他进程的占用（读 `/proc/locks` 快照，只用于排序；真正分配以 try-lock 为准）。
- **fork**：锁 fd 带 `O_CLOEXEC`；只 fork 不 exec 的子进程在 `pthread_atfork` child 回调中关闭继承的线程/预留锁，不会延长父进程的占用。`excludeCpus` 的锁例外，由子进程继承并保持，父进程退出后子进程的排除核仍受保护。`ThreadCpuLease` 的线程登记表随 fork 复制，子进程应在新线程里绑核。
- 行为与 Local 一致，区别只在范围：`excludeCpus`、`avoidFirstCoreOfNumaNode`、`smt` 两种组件含义相同。同一进程不能混用两种组件（抛 `std::logic_error`）。
- **限制**：只有使用同一锁目录的进程之间才协商；不同容器的 `/dev/shm` 互相隔离，需挂载同一目录；不支持 NFS 等网络文件系统。不用 tm_kit 的第三方进程不参与协商，仍需 `excludeCpus` 避让。能写锁目录的本机用户都能占住锁文件，目录权限由部署方负责。非 Linux 平台使用 CrossProcess 抛异常。

### 自写线程复用绑核（ThreadCpuLease）

自己创建的线程（例如自写 importer 的收包线程）可以复用同一个分配器，从而与图节点共享“不抢同一个核”的保证：

```cpp
void run() {   // 自己线程函数的第一行
    auto lease = infra::ThreadCpuLease::bindCurrentThread<Env>("nic-rx");
    // auto lease = infra::ThreadCpuLease::bindCurrentThreadOnNuma<Env>(1, "nic-rx");
    // auto lease = infra::ThreadCpuLease::bindCurrentThreadTo<Env>({20}, "legacy");
    // ... 忙循环 ...
}   // 正常返回或抛异常退出都会归还 CPU
```

- 三个入口各有独立名字，分别对应全局自动、限定 NUMA 节点、手工指定 CPU；也都有接收 `IThreadCpuAllocator &` 的重载。
- 只作用于**调用线程**，所以在线程函数里直接调用即可，不依赖线程句柄，也不存在句柄失效问题。
- RAII：租约可移动、不可拷贝；析构、`reset()` 或移动赋值时归还 CPU。
- 失败一律抛 `ThreadCpuBindError`；Environment 没有分配器组件时 `static_assert` 编译失败。
- **多线程安全**：选核在分配器内部加锁，每个线程只改自己的亲和性，任意多个线程可同时调用。同一线程同时只能持有一个 `bindCurrentThread*` 租约，再次绑定会抛异常，避免一个线程悄悄占两个核。单个租约对象本身不应被两个线程同时操作（与标准库对象一致）。

图节点内部的租约（`ThreadCpuLease::adopt`）与用户线程共用同一套归还逻辑；节点析构时先 join 线程再归还 CPU。

### SharedPool：显式选择与进程级配置

`basic::RealTimeSharedPoolExecutorComponent` 继承选择组件（`tm_basic/tm_kit/basic/RealTimeSharedPoolExecutor.hpp:518`）。把它作为 Environment 的一个组件即可选择共享池。示例代码库 `tm_examples` 中暂无用例；真实配置签名与默认值见同一头文件的 `:63`、`:247`：

```cpp
struct SharedThreadPoolConfig {
    unsigned threadCount = 0;
    std::vector<int> cpus;
    std::chrono::nanoseconds idleTick = std::chrono::milliseconds(1);
    unsigned maxBatch = 64;
    std::chrono::nanoseconds spinWait = std::chrono::microseconds(200);
};
// SharedThreadPool 的公开静态成员：
static void configure(SharedThreadPoolConfig const &cfg);
```

`threadCount=0` 使用 `hardware_concurrency()`（至少一个线程）；Linux 下 `cpus` 非空时按循环分配绑核。必须在首个池执行器节点构造前 `configure`，池启动后修改会抛 `std::logic_error`。每次 slice 最多处理 `maxBatch` 项，再把仍有工作的 strand 重新调度，避免一个繁忙节点永久占用池线程。

idle 由池级 `idleTick` 驱动，只登记有 idle work 的节点；没有活跃 idle 节点时计时线程阻塞。`spinWait` 是处理后的有界自旋预算，空 idle tick 不会重置该预算；共享池采用池级配置而非逐节点选项。

### Moodycamel：可选依赖与顺序取舍

`tm_basic/tm_kit/basic/MoodycamelThreadedExecutor.hpp:125` 的真实模板为：

```cpp
template <class Item, class Config = infra::DedicatedThreadExecutorConfig>
class MoodycamelThreadedExecutor;
```

Environment 选择组件是 `basic::MoodycamelThreadedExecutorComponent`（同一头文件 `:289`）。示例代码库中暂无用例；实际集成与并发场景在 `tm_basic/test/moodycamel_executor_test/`。

最终实现融合原 Enhanced 路径，使用可复用块、单消费者 token、八分片发布计数和睡眠握手；不是旧的 `BlockingConcurrentQueue` 加 optional 唤醒 token 实现。块大小为 256。消费者活跃时不为每条消息无条件加通知锁；有 idle work 时按 `Config::idlePeriod` 等待，没有时可阻塞到数据、stop 或 wakeIdle。`ThreadedExecOptions::spinWait` 默认 200µs，是处理后有界主动等待，设为零可关闭；`Config::spinBeforeSleep` 默认零。逐节点 `ThreadedNodeOptions::spinWait` 覆盖构造时传入的值，从消费者下一次等待起生效。

**跨生产者全局 FIFO 已放弃。** 开启 `CheckTimeComponent<true>` 后，跨生产者到达的时间戳重排仍可能被时间检查丢弃；即使时间检查关闭，有状态的 `VersionChecker` 仍会拒绝旧版本。不要把默认时间检查关闭理解为关闭版本检查。

头文件通过 `__has_include` 接受 "concurrentqueue/moodycamel/concurrentqueue.h" 或 "moodycamel/concurrentqueue.h"。仅当 `TM_KIT_BASIC_HAS_MOODYCAMEL_THREADED_EXECUTOR` 已定义时才有执行器及组件声明；缺失依赖时头文件可以包含，但不能引用这些类型。`TM_KIT_BASIC_DISABLE_MOODYCAMEL_THREADED_EXECUTOR` 可禁用声明。

Meson 的 feature 选项 `moodycamel_executor`（`tm_basic/meson_options.txt:1`）控制本项目测试与基准目标：`auto` 探测头文件，`enabled` 缺失时报错，`disabled` 跳过相关目标并定义禁用宏。公共头文件仍安装，下游按自己的 include 路径和宏判断可用性。构建入口见 [BUILD.md](../BUILD.md)。

### 缓冲诊断与 idle 唤醒

`OutputRealTimeThreadBufferSizeComponent` 让 handler 设置 `trackPendingCount=true`，按批次记录缓冲计数。默认 Dedicated 报告 splice 批次大小；Moodycamel 使用发布前维护的 pending 计数，不能把不同执行器的诊断值解释为完全相同的队列快照。

`setIdleWorkerForAction` 可以在 action 构造启动后调用；setter 先在锁内更新 worker 与原子 `hasIdleWorker_`，再调用 `wakeIdle()`，以唤醒可能无限期睡眠的执行器（`tm_infra/tm_kit/infra/RealTimeApp.hpp:1111`）。Inline 不运行 idle worker，不能靠为 threaded handler 选 Inline 来保留异步 idle 语义。

## 最小可用示例与兼容接口

`tm_examples` 中暂无替换执行器的用例，本节只列已核实的公开声明。原有 `ThreadedHandler` 仍是公开**类包装**（`tm_infra/tm_kit/infra/RealTimeApp.hpp:354`）：

```cpp
template <class T, class W>
class ThreadedHandler : public ExecHandler<T, W, ThreadedPolicy> {};
```

它保留具体 Environment 派生类中 `H() : ThreadedHandler() {}` 和 `ThreadedHandler::startThread()` 等注入类名用法，不能再次简单改为别名。回归测试在 `tm_infra/test/threaded_handler_test/ThreadedHandlerCompatibilityTest.cpp`。

普通继承者继续使用 `startThread()`、`threadHandle()` 和 protected `putData()`、`timeCheckGood()`、`timeChecker()`、`stop()`、`wakeIdle()`；host 的 `waitForStart()`、`actuallyHandle()`、`idleWork()` 由适配器转发，`hasIdleWork()` 可选，缺省按有 idle work 处理。variant 2–20 路的分派由 `ExecHandler` 特化实现。自定义 `actuallyHandle()` 若需要输入检查，仍须调用 `timeCheckGood()`；仅入队不会自动替代这个检查。

迁移边界：infra 原 `ThreadedHandlerBase` 已被统一的核心实现取代，`BusyLoopThreadedHandler` / `BusyLoopThreadedHandlerBase`、`ThreadedExecMode` 已删除；basic 的旧 Enhanced、Legacy 公开入口也不保留兼容别名。共享池头文件和类型现在属于 basic。`ChainPollingPolicy::BusyLoop()` 仍有效，ChainWriter 使用自己的本地 handler，见 [共享链](../tm_basic/08-shared-chain.md)。

## 实时 / 回测行为差异

| 维度 | RealTimeApp | SinglePass / TopDownSinglePass |
|---|---|---|
| 本文执行器策略 | 生效 | 不使用 |
| `SuggestThreaded` | 为基于 handler 的节点选择策略 | 忽略 |
| 默认时间检查 | 关闭，可显式启用 | 同样关闭，可显式启用 |
| 输出时间戳与回测调度 | 仍由 Environment 和图逻辑决定 | 执行器组件不改变单线程迭代或时间排序 |

## 易错点

- `kOwnContext` 表示“不同执行上下文”，不等于“节点独占固定 OS 线程”；共享池也返回 true。
- `stop()` 不是 join 或 drain：它是非阻塞的，也不排空待处理数据。**join 发生在执行器析构**：`DedicatedThreadExecutor` 与 `MoodycamelThreadedExecutor` 在析构中先 `stop()` 再 `join()`，所以显式 `delete` 一个执行器/节点后会等到其线程退出；执行器从自己的回调内被析构时无法自 join，退化为 detach，线程在回调返回后自行退出。其他自带线程的节点（`SimpleImporter`、`BunchedImporter`、`ChainReader`/`ChainWriter`、`CommonFlowUtils` 中的节点、`SharedThreadPool`）仍是 detached。host / Environment / 回调访问的资源必须覆盖回调期。SharedPool 的 executor 析构会同步正在运行的 slice（自身回调内析构有专门处理），也不能据此声称整个图可任意安全析构。
- 切换 SharedPool 或 Inline 前核对回调里的阻塞、重入与共享状态；原生线程句柄可能不存在。
- 多个 tm_kit 进程同机运行时，只挂 `HwlocThreadCpuAllocatorComponent` 不会跨进程协商，忙线程可能落在同一核；需要换成 `HwlocCrossProcessCpuAllocatorComponent`。
- 性能数据依赖负载、CPU 绑定、SMT 与自旋预算，不把历史 benchmark 的单次结果作为 API 保证。

## 第三方依赖

infra 的 Inline / Dedicated 以及 basic 的 SharedPool 只使用标准库（绑核使用 Linux API）；Moodycamel 适配器可选依赖 [concurrentqueue](https://github.com/cameron314/concurrentqueue)。它们都不会成为 tm_infra 的依赖。

自动绑核：infra 只提供扩展点（零依赖）；hwloc 实现属于 basic 的可选功能，依赖 [hwloc](https://www.open-mpi.org/projects/hwloc/)（vcpkg port 名 `hwloc`）。tm_basic 通过 Meson feature 选项 `hwloc_cpu_allocator`（`auto` 探测）决定是否可用；未安装时相关测试目标被跳过，公共头文件仍会安装但不声明执行器类型。

## 相关章节

- [App 类型](01-app-types.md) · [Environment](02-environments.md) · [节点提升](03-nodes-and-lifting.md)
- [时间与版本检查](07-time-and-data.md) · [生成片段](09-generated-pieces.md)
- [共享链](../tm_basic/08-shared-chain.md) · [传输并发](../tm_transport/08-concurrency.md)
- [跨库模式](../PATTERNS.md#41-实时模式的线程取决于节点与执行器)
