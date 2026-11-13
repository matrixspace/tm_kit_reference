---
title: 实时 handler 与可替换执行器
library: tm_infra
headers: [tm_kit/infra/RealTimeThreadedExecutor.hpp, tm_kit/infra/RealTimeApp.hpp, tm_kit/basic/RealTimeSharedPoolExecutor.hpp, tm_kit/basic/MoodycamelThreadedExecutor.hpp, tm_kit/basic/RealTimeMPSCQueue.hpp]
keywords: [ThreadedHandler, ExecHandler, HandlerPolicy, ThreadedPolicy, InlinePolicy, InlineExecutor, DedicatedThreadExecutor, RealTimeThreadedExecutorComponent, RealTimeThreadedExecutorFor, RealTimeSharedPoolExecutor, RealTimeSharedPoolExecutorComponent, SharedThreadPool, SharedThreadPoolConfig, MoodycamelThreadedExecutor, MoodycamelThreadedExecutorComponent, ThreadedExecOptions, ThreadedNodeOptions, configureThreadedNode, configureThread, spinWait, 绑核, Cpus, CpuAutoBind, CpuAutoBindOnNuma, reserveReplacing, IThreadCpuAllocator, ThreadCpuAllocatorComponent, ThreadCpuLease, CpuBind, fromCpuBindString, bindCurrentThreadBy, CpuBindingSpec, CpuBindKind, parseCpuList, cpusFromString, 绑核字符串, NUMA, kOwnContext, kSerialCallbacks, wakeIdle, threadHandle, 执行器, 线程池, 共享线程池, 同步执行, FIFO顺序, strand, FIFO, concurrentqueue, moodycamel_executor]
---

# 实时 handler 与可替换执行器

## 用途

`RealTimeApp` 把节点逻辑和调度方式分开：统一的 `ExecHandler` 负责数据分派、时间与版本检查，执行器（executor）决定是在调用线程同步处理、专用线程处理，还是交给共享线程池。通过 Environment 选择执行器，无需为 action、exporter、facility 各维护同步与异步两份实现。

本文对应 2026-11-12 的 `develop` 源码（含逐节点 spinWait/绑核、CpuAutoBind 与字符串绑核策略）；具体 commit 见 [VERSIONS.json](../VERSIONS.json)。默认执行器是 **infra 的 mutex/list `DedicatedThreadExecutor`**。早期开发记录中的默认 MPSC、Enhanced 执行器和带 `ThreadedExecMode` 的契约均为历史方案。

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

`ExecHandlerCore::configureWithLease` 调用 `reserveReplacing` 时把节点当前租约的 CPU 作为 `previous` 传入。Environment 没有挂分配器组件时，`CpuAutoBind()` 在节点上抛异常并提示需要的组件。

**hwloc 实现在 tm_basic**（`tm_basic/tm_kit/basic/HwlocThreadCpuAllocator.hpp`，可选依赖 hwloc），提供两个组件：

| 组件 | 协商范围 |
|---|---|
| `basic::HwlocThreadCpuAllocatorComponent` | 本进程内（默认） |
| `basic::HwlocCrossProcessCpuAllocatorComponent` | 同机所有使用同一锁目录的 tm_kit 进程（flock 每核一个锁文件，进程退出即释放） |

要点：按物理核分配，遵守 taskset/numactl/cgroup，默认避开 SMT 兄弟和 NUMA 首核；`excludeCpus` 所在核任何方式都不能绑定；显式 `Cpus()` 与自动分配、或两个显式绑定落在同一物理核时抛异常；**失败一律抛异常**，不静默降级（这与 spinWait/`Cpus()` “不支持就返回 false”的约定不同）。分配规则、配置项、跨进程协商机制、fork 行为与限制详见 [tm_basic · hwloc 线程绑核分配器](../tm_basic/11-hwloc-cpu-allocator.md)。

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

### 字符串绑核策略（CpuBind）

绑核策略常来自配置文件或命令行。一个字符串即可选择上面几种方式，节点和自建线程用同一套语法（`tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp`）：

| 字符串 | 含义 | 等价调用 |
|---|---|---|
| `""` / `"none"` | 不绑定，保持现有绑核 | 不调用 |
| `"auto"` | 全局自动选核 | `CpuAutoBind()` / `bindCurrentThread` |
| `"numa:1"` | 只在 NUMA 节点 1 内自动选核 | `CpuAutoBindOnNuma(1)` / `bindCurrentThreadOnNuma` |
| `"cpus:2,3,8-11"` | 显式 CPU 列表 | `Cpus({2,3,8,9,10,11})` / `bindCurrentThreadTo` |
| `"8-11"`、`"2,3"` | `cpus:` 的简写 | 同上 |

```cpp
M::configureThreadedNode(node, ThreadedNodeOptions().CpuBind(cfg.nodeCpu));      // 链式
M::configureThreadedNode(node, ThreadedNodeOptions::fromCpuBindString("numa:1")); // 工厂
auto lease = infra::ThreadCpuLease::bindCurrentThreadBy<Env>(cfg.rxCpu, "nic-rx"); // 自建线程
// 也有接收 IThreadCpuAllocator & 的重载：bindCurrentThreadBy(alloc, spec, who)
```

底层类型与工具：

```cpp
std::vector<int> parseCpuList(std::string const &);   // "2,3,8-11"、"2:5" → CPU 列表
enum class CpuBindKind { None, Auto, AutoOnNuma, Cpus };
struct CpuBindingSpec {
    CpuBindKind kind; std::optional<int> numaNode; std::vector<int> cpus;
    static CpuBindingSpec parse(std::string const &);
};
```

语义要点：

- 关键字大小写不敏感，首尾空白忽略；范围可用 `-` 或 `:`，逗号分隔的每项两侧可有空白（`"2 - 4"` 合法）。
- **校验是严格的**：每个数字必须是完整的非负十进制数，`"cpus:2foo"`、`"2-3-8"`、`"numa:1,2"`、`"-1"`、`"+2"`、超出 `INT_MAX` 的值、`lo > hi` 的范围和未知关键字一律抛 `std::invalid_argument`，不会只取数字前缀。范围展开到 `INT_MAX` 也不会溢出。
- `"none"` 不清除已有绑核：`Cpus({4}).CpuBind("none")` 仍保留 CPU 4，与“空 `cpus` 不清除绑核”的约定一致。`"cpus:"`（空列表）按 none 处理。
- `bindCurrentThreadBy<Env>` 对 `"none"` / `""` 返回非激活租约，不访问分配器；Environment **没有**分配器组件时仍能编译，只有真正请求绑核（`auto`/`numa:`/`cpus:`）时才在运行时抛 `ThreadCpuBindError`。这一点不同于三个具名入口的 `static_assert`，便于同一份代码在不启用绑核的环境下复用。
- 解析出的策略随后走原有路径，所以分配规则、冲突检测和“失败抛异常”的行为与具名接口完全相同。

tm_basic 的配置串复用同一个 `parseCpuList`：`SharedThreadPoolConfig::cpusFromString`（见下节）和 `HwlocCpuAllocatorConfig::fromString`（见 [tm_basic/11](../tm_basic/11-hwloc-cpu-allocator.md#配置)）。

tm_transport 的 IPC 传输内部线程（接收/轮询线程、multicast/singlecast 发送线程、aeron 内嵌 driver）也用同一套语法，通过 ConnectionLocator 属性 `cpu` / `senderCpu` / `driverCpu` 绑核，默认走 `bindCurrentThreadBy<Env>`，见 [tm_transport · transport 线程绑核](../tm_transport/00-overview.md#6-transport-线程绑核)。

### SharedPool：显式选择与进程级配置

`basic::RealTimeSharedPoolExecutorComponent` 继承选择组件（`tm_basic/tm_kit/basic/RealTimeSharedPoolExecutor.hpp:518`）。把它作为 Environment 的一个组件即可选择共享池。示例代码库 `tm_examples` 中暂无用例；真实配置签名与默认值见同一头文件的 `:63`、`:247`：

```cpp
struct SharedThreadPoolConfig {
    unsigned threadCount = 0;
    std::vector<int> cpus;
    std::chrono::nanoseconds idleTick = std::chrono::milliseconds(1);
    unsigned maxBatch = 64;
    std::chrono::nanoseconds spinWait = std::chrono::microseconds(200);
    // "2-5"、"cpus:2,3"；"none"/"" 清空 cpus；返回 *this，非法串抛 std::invalid_argument
    SharedThreadPoolConfig &cpusFromString(std::string const &s);
};
// SharedThreadPool 的公开静态成员：
static void configure(SharedThreadPoolConfig const &cfg);
```

`cpusFromString` 只接受 `none` 和 CPU 列表；`auto`、`numa:` 对池线程没有意义，会抛异常。注意它对 `"none"` 是**清空** `cpus`，与节点级 `CpuBind("none")` 的“保持不变”不同。

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
| `configureThreadedNode` | 生效（有专用线程的节点返回 true，否则返回 false） | 编译通过，始终返回 false（no-op） |

`SinglePassIterationApp`、`TopDownSinglePassIterationApp`、`BasicWithTimeApp` 均已提供与 `RealTimeApp::configureThreadedNode` 签名兼容的 no-op 静态方法，使同一份图构建代码无需 `#ifdef` 即可在实时和回测模式下复用。

## 易错点

- `kOwnContext` 表示“不同执行上下文”，不等于“节点独占固定 OS 线程”；共享池也返回 true。
- `stop()` 不是 join 或 drain：它是非阻塞的，也不排空待处理数据。**join 发生在执行器析构**：`DedicatedThreadExecutor` 与 `MoodycamelThreadedExecutor` 在析构中先 `stop()` 再 `join()`，所以显式 `delete` 一个执行器/节点后会等到其线程退出；执行器从自己的回调内被析构时无法自 join，退化为 detach，线程在回调返回后自行退出。其他自带线程的节点（`SimpleImporter`、`BunchedImporter`、`ChainReader`/`ChainWriter`、`CommonFlowUtils` 中的节点、`SharedThreadPool`）仍是 detached。host / Environment / 回调访问的资源必须覆盖回调期。SharedPool 的 executor 析构会同步正在运行的 slice（自身回调内析构有专门处理），也不能据此声称整个图可任意安全析构。
- 切换 SharedPool 或 Inline 前核对回调里的阻塞、重入与共享状态；原生线程句柄可能不存在。
- 多个 tm_kit 进程同机运行时，只挂 `HwlocThreadCpuAllocatorComponent` 不会跨进程协商，忙线程可能落在同一核；需要换成 `HwlocCrossProcessCpuAllocatorComponent`（见 [tm_basic/11](../tm_basic/11-hwloc-cpu-allocator.md)）。
- 性能数据依赖负载、CPU 绑定、SMT 与自旋预算，不把历史 benchmark 的单次结果作为 API 保证。

## 第三方依赖

infra 的 Inline / Dedicated 以及 basic 的 SharedPool 只使用标准库（绑核使用 Linux API）；Moodycamel 适配器可选依赖 [concurrentqueue](https://github.com/cameron314/concurrentqueue)。它们都不会成为 tm_infra 的依赖。

自动绑核：infra 只提供扩展点（零依赖）；hwloc 实现属于 basic 的可选功能（[tm_basic/11](../tm_basic/11-hwloc-cpu-allocator.md)），依赖 [hwloc](https://www.open-mpi.org/projects/hwloc/)（vcpkg port 名 `hwloc`）。tm_basic 通过 Meson feature 选项 `hwloc_cpu_allocator`（`auto` 探测）决定是否可用；未安装时相关测试目标被跳过，公共头文件仍会安装但不声明执行器类型。

## 相关章节

- [App 类型](01-app-types.md) · [Environment](02-environments.md) · [节点提升](03-nodes-and-lifting.md)
- [时间与版本检查](07-time-and-data.md) · [生成片段](09-generated-pieces.md)
- [共享链](../tm_basic/08-shared-chain.md) · [传输并发](../tm_transport/08-concurrency.md)
- [跨库模式](../PATTERNS.md#41-实时模式的线程取决于节点与执行器)
- [hwloc 线程绑核分配器](../tm_basic/11-hwloc-cpu-allocator.md)
- [transport 线程绑核](../tm_transport/00-overview.md#6-transport-线程绑核)
