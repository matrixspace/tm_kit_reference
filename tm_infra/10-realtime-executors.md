---
title: 实时 handler 与可替换执行器
library: tm_infra
headers: [tm_kit/infra/RealTimeThreadedExecutor.hpp, tm_kit/infra/RealTimeApp.hpp, tm_kit/basic/RealTimeSharedPoolExecutor.hpp, tm_kit/basic/MoodycamelThreadedExecutor.hpp, tm_kit/basic/RealTimeMPSCQueue.hpp]
keywords: [ThreadedHandler, ExecHandler, HandlerPolicy, ThreadedPolicy, InlinePolicy, InlineExecutor, DedicatedThreadExecutor, RealTimeThreadedExecutorComponent, RealTimeThreadedExecutorFor, RealTimeSharedPoolExecutor, RealTimeSharedPoolExecutorComponent, SharedThreadPool, SharedThreadPoolConfig, MoodycamelThreadedExecutor, MoodycamelThreadedExecutorComponent, ThreadedExecOptions, kOwnContext, kSerialCallbacks, wakeIdle, threadHandle, 执行器, 线程池, 共享线程池, 同步执行, FIFO顺序, strand, FIFO, concurrentqueue, moodycamel_executor]
---

# 实时 handler 与可替换执行器

## 用途

`RealTimeApp` 把节点逻辑和调度方式分开：统一的 `ExecHandler` 负责数据分派、时间与版本检查，执行器（executor）决定是在调用线程同步处理、专用线程处理，还是交给共享线程池。通过 Environment 选择执行器，无需为 action、exporter、facility 各维护同步与异步两份实现。

本文对应 2026-11-09 合并到本地 `develop` 的最终源码；具体 commit 见 [VERSIONS.json](../VERSIONS.json)。默认执行器是 **infra 的 mutex/list `DedicatedThreadExecutor`**。早期开发记录中的默认 MPSC、Enhanced 执行器和带 `ThreadedExecMode` 的契约均为历史方案。

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

host 适配器提供 `executorWaitForStart()`、`executorHandle(...)`、`executorIdleWork()`、`executorHasIdleWork()`、`executorBeforeBatch(...)`。Inline 不调用启动等待或 idle 回调。异步执行器的 idle 只在没有待处理数据时运行。

每生产者 FIFO 是基本要求；跨生产者的顺序必须看具体实现。`kSerialCallbacks=false` 时，框架使用保护版 `TimeChecker<true,T>`；为 true 时使用非保护版。见 `tm_infra/tm_kit/infra/RealTimeApp.hpp:288` 和 [时间检查](07-time-and-data.md#时间倒流检查timechecker-与-checktimecomponent)。**时间检查的互斥量不保护业务回调自身的共享状态。**

### 四种实现的差异

| 执行器 | 每节点上下文 | 同一 host 回调串行 | 跨生产者全局 FIFO | `threadHandle()` |
|---|---|---|---|---|
| `infra::InlineExecutor<Item>` | 无，直接在调用线程执行 | 否，多生产者可并发进入 | 无串行队列 | `nullopt` |
| `infra::DedicatedThreadExecutor<Item, Config>` | 一条专用线程，默认 | 是 | 保留 mutex 入队线性化顺序 | 原生线程句柄 |
| `basic::RealTimeSharedPoolExecutor<Item>` | 进程共享池，每节点一个 strand | 是，同一节点回调不重叠 | 保留该节点 MPSC 入队线性化顺序 | `nullopt` |
| `basic::MoodycamelThreadedExecutor<Item, Config>` | 一条专用线程，可选 | 是 | **不保证**，仅每生产者 FIFO | 原生线程句柄 |

SharedPool 的 strand（串行执行单元）允许节点在不同池线程之间迁移，不能依赖 per-node `thread_local`、固定线程 ID 或逐节点绑核。不同节点仍可并发；两个节点共享业务状态时仍需同步。阻塞 IO、长时间重试或等待启动屏障会占住池线程，应保留专用线程。

### 默认 Dedicated：保留 mutex/list，修复空等

定义见 `tm_infra/tm_kit/infra/RealTimeThreadedExecutor.hpp:100`。生产者在 mutex 下追加 `std::list<Item>`，消费者把整批 `splice` 到本地处理列表。等待带 predicate：若处理期间又有数据入队，下一轮立即处理，不再无条件白等 1ms。这项修复针对该执行器；未覆盖自带线程的 trigger / bunched / simple importer 的其他等待路径。

`DedicatedThreadExecutorConfig::idlePeriod` 默认 1ms；保持历史周期 idle 行为，即使 `executorHasIdleWork()` 为 false 仍周期回调。默认实现忽略 `ThreadedExecOptions::spinWait` 和 `Config::spinBeforeSleep`，不能用这些字段让默认执行器忙等。

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

最终实现融合原 Enhanced 路径，使用可复用块、单消费者 token、八分片发布计数和睡眠握手；不是旧的 `BlockingConcurrentQueue` 加 optional 唤醒 token 实现。块大小为 256。消费者活跃时不为每条消息无条件加通知锁；有 idle work 时按 `Config::idlePeriod` 等待，没有时可阻塞到数据、stop 或 wakeIdle。`ThreadedExecOptions::spinWait` 默认 200µs，是处理后有界主动等待，设为零可关闭；`Config::spinBeforeSleep` 默认零。

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
- `stop()` 不是 join 或 drain。Dedicated、Moodycamel 的线程 detached；共享执行器状态的存活不保证 host 存活，host / Environment / 回调访问的资源必须覆盖回调期。SharedPool 的 executor 析构会同步正在运行的 slice（自身回调内析构有专门处理），也不能据此声称整个图可任意安全析构。
- 切换 SharedPool 或 Inline 前核对回调里的阻塞、重入与共享状态；原生线程句柄可能不存在。
- 性能数据依赖负载、CPU 绑定、SMT 与自旋预算，不把历史 benchmark 的单次结果作为 API 保证。

## 第三方依赖

infra 的 Inline / Dedicated 以及 basic 的 SharedPool 只使用标准库（绑核使用 Linux API）；Moodycamel 适配器可选依赖 [concurrentqueue](https://github.com/cameron314/concurrentqueue)。它不会成为 tm_infra 的依赖。

## 相关章节

- [App 类型](01-app-types.md) · [Environment](02-environments.md) · [节点提升](03-nodes-and-lifting.md)
- [时间与版本检查](07-time-and-data.md) · [生成片段](09-generated-pieces.md)
- [共享链](../tm_basic/08-shared-chain.md) · [传输并发](../tm_transport/08-concurrency.md)
- [跨库模式](../PATTERNS.md#41-实时模式的线程取决于节点与执行器)
