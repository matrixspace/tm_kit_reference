---
title: hwloc 线程绑核分配器（HwlocThreadCpuAllocator）
library: tm_basic
headers: [tm_kit/basic/HwlocThreadCpuAllocator.hpp]
keywords: [HwlocThreadCpuAllocator, HwlocThreadCpuAllocatorComponent, HwlocCrossProcessCpuAllocatorComponent, HwlocCpuAllocatorConfig, CpuAllocatorScope, crossProcessLockDir, excludeCpus, avoidFirstCoreOfNumaNode, SmtPolicy, RequireFullCore, AllowPartialCore, CpuAutoBindError, reserveReplacing, CpuAutoBind, ThreadCpuLease, 绑核, 自动绑核, 多进程协商, flock, hwloc, NUMA, SMT, hwloc_cpu_allocator, fromString, 绑核字符串, bindCurrentThreadBy]
---

# hwloc 线程绑核分配器（HwlocThreadCpuAllocator）

## 用途

tm_infra 的 `ThreadedNodeOptions().CpuAutoBind()` 和 `infra::ThreadCpuLease` 只定义了扩展点 `IThreadCpuAllocator`，本身不挑核（见 [实时执行器 · 自动绑核](../tm_infra/10-realtime-executors.md#自动绑核cpuautobind)）。tm_basic 用 hwloc 提供了实现 `basic::HwlocThreadCpuAllocator`，并给出两个 Environment 组件：

| 组件 | 协商范围 |
|---|---|
| `basic::HwlocThreadCpuAllocatorComponent` | 本进程内的线程（默认） |
| `basic::HwlocCrossProcessCpuAllocatorComponent` | 同一台机器上使用同一锁目录的所有 tm_kit 进程（可选开启） |

两种组件共用同一个进程单例和同一份配置，规则完全一致，区别只在“进程内”还是“跨进程”。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/HwlocThreadCpuAllocator.hpp>
// namespace dev::cd606::tm::basic
```

头文件用 `__has_include(<hwloc.h>)` 探测，探测到才定义 `TM_KIT_BASIC_HAS_HWLOC_CPU_ALLOCATOR` 并声明下列类型；也可以定义 `TM_KIT_BASIC_DISABLE_HWLOC_CPU_ALLOCATOR` 强制关闭。Meson 选项见 [构建](../BUILD.md)（`hwloc_cpu_allocator`）。

## 核心类型与签名

```cpp
enum class SmtPolicy { RequireFullCore, AllowPartialCore };

struct HwlocCpuAllocatorConfig {
    std::vector<int> excludeCpus;                 // 永不分配，按整个物理核生效
    bool avoidFirstCoreOfNumaNode = true;         // 跳过每个 NUMA 节点的首核
    SmtPolicy smt = SmtPolicy::RequireFullCore;
    std::string crossProcessLockDir = "/dev/shm/tm_kit_cpu_locks";   // 仅 CrossProcess
};

enum class CpuAllocatorScope { Local, CrossProcess };

class CpuAutoBindError : public std::runtime_error;

class HwlocThreadCpuAllocator final : public infra::IThreadCpuAllocator {
public:
    static void configure(HwlocCpuAllocatorConfig const &cfg);
    static void configure(HwlocCpuAllocatorConfig const &cfg, CpuAllocatorScope scope);
    static HwlocThreadCpuAllocator &instance();
    static HwlocThreadCpuAllocator &instanceFor(CpuAllocatorScope s);
    // acquire / reserve / reserveReplacing / release：实现 IThreadCpuAllocator
    // 独立实例（测试或自定义组件用），scope 在构造时固定
    explicit HwlocThreadCpuAllocator(HwlocCpuAllocatorConfig cfg = {}, CpuAllocatorScope scope = CpuAllocatorScope::Local);
};

struct HwlocThreadCpuAllocatorComponent;         // Local
struct HwlocCrossProcessCpuAllocatorComponent;   // CrossProcess
```

### 配置

```cpp
struct Env : ..., basic::HwlocThreadCpuAllocatorComponent {};

basic::HwlocCpuAllocatorConfig cfg;
cfg.excludeCpus = {8, 9};        // 第三方库已占用的 CPU（整核避让）
basic::HwlocThreadCpuAllocator::configure(cfg);
```

- `configure()` 必须在首次使用前调用，之后再调用抛 `std::logic_error`（与 `SharedThreadPool::configure` 相同）。
- 首次加载拓扑失败（例如 `excludeCpus` 含不可用或不存在的 CPU）会整体回滚，不留半成品状态；此时分配器仍算“未使用”，可以再次 `configure()` 修正后重试。
- 未挂分配器组件就调用 `CpuAutoBind()` 时，节点抛异常并提示需要的组件；`ThreadCpuLease::bindCurrentThread<Env>` 则 `static_assert` 编译失败。字符串入口 `bindCurrentThreadBy<Env>` 例外：`"none"` 可以编译并返回非激活租约，真正请求绑核时运行时抛 `ThreadCpuBindError`（见 [实时执行器 · 字符串绑核策略](../tm_infra/10-realtime-executors.md#字符串绑核策略cpubind)）。

#### 从字符串配置（fromString）

配置来自配置文件或命令行时，可以用一个分号分隔的 `key=value` 串构造：

```cpp
static HwlocCpuAllocatorConfig fromString(std::string const &s,
                                          CpuAllocatorScope *scopeOut = nullptr);

basic::CpuAllocatorScope scope = basic::CpuAllocatorScope::Local;
auto cfg = basic::HwlocCpuAllocatorConfig::fromString(
    "exclude=8,9;smt=partial;scope=cross;lockdir=/dev/shm/my_locks", &scope);
basic::HwlocThreadCpuAllocator::configure(cfg, scope);
```

| key | 取值 | 对应字段 |
|---|---|---|
| `exclude` | CPU 列表，与 `parseCpuList` 同语法（`8,9`、`4-7`） | `excludeCpus`（整体替换） |
| `avoid_first` | `0` / `false` / `no` 关闭，其他任何值都视为开启 | `avoidFirstCoreOfNumaNode` |
| `smt` | `partial`（或 `allow_partial`）/ `require_full`（或 `full`） | `smt` |
| `scope` | `local` / `cross`（或 `cross_process`） | 写入 `*scopeOut` |
| `lockdir` | 路径，原样使用 | `crossProcessLockDir` |

- key 和枚举值大小写不敏感，每项两侧空白忽略；空串返回默认配置。未写的 key 保持默认值。
- 未知 key、缺少 `=`、非法 `smt`/`scope` 值抛 `std::invalid_argument`。`exclude` 的校验与 tm_infra 解析器一致，`exclude=8foo`、`exclude=8-9-10`、`exclude=-1` 都会抛异常。
- `scopeOut` 为空指针时 `scope=` 项**被忽略，取值也不校验**。需要 scope 时务必传入指针，并用带 scope 的 `configure(cfg, scope)`。
- `fromString` 只构造配置，不调用 hwloc；拓扑相关的错误（例如排除了不存在的 CPU）仍在 `configure()` / 首次使用时报告。

## 分配规则

1. **可用 PU** = `hwloc_get_cpubind(PROCESS)` ∩ `hwloc_topology_get_allowed_cpuset`，因此 taskset、`numactl --physcpubind/--cpunodebind` 和 cgroup cpuset 都会被遵守。拓扑以 `HWLOC_TOPOLOGY_FLAG_INCLUDE_DISALLOWED` 加载，被掩码禁用的 SMT 兄弟仍留在核里，所以“每核只暴露一个 PU”的掩码在 `RequireFullCore` 下会被判为没有完整核，而不是误当成整核。
2. **以物理核为单位**分配，一个核只给一个忙线程。默认 `RequireFullCore` 要求核的所有 PU 都可用；`AllowPartialCore` 放松这一点。
3. 每个 NUMA 节点的**首核**默认避开（`avoidFirstCoreOfNumaNode`）：它承载该节点的中断与内核杂务。
4. **NUMA 选择**默认“集中”：先留在已有自动分配、且仍有空闲核的节点；其次是线程 membind 为 BIND 策略时指定的节点；最后按空闲核数排序。`CpuAutoBindOnNuma(n)` 只在节点 n 内挑。
5. **显式预留**：显式 `Cpus()`（Environment 挂了分配器时）和 `ThreadCpuLease::bindCurrentThreadTo` 登记为预留，自动分配避开整核。预留与已自动分配的核、或与另一个显式预留**落在同一物理核**时抛 `CpuAutoBindError`——自动分配了 CPU 2 之后再预留它的 SMT 兄弟 CPU 30 同样报错，隔离保证不依赖配置顺序。同一节点用相同 CPU 重配置不算冲突（`reserveReplacing` 把节点当前的 CPU 作为 previous 传入）。预留不可用 CPU 也抛异常。
6. **`excludeCpus` 所在物理核任何方式都不能绑定**：自动分配跳过它；显式 `Cpus()` 和 `bindCurrentThreadTo` 绑到它（含 SMT 兄弟）抛 `CpuAutoBindError`。列表中任一 CPU 被拒，整次调用不登记任何预留。

**失败一律抛异常**，不静默降级：没有可用核、NUMA 节点不存在或不可用、`excludeCpus` 写了不可用的 CPU 等，都会抛出带诊断的异常（列出可用 PU、被排除的核、已分配 CPU，CrossProcess 下还列出被其他进程占用的核）。

## 多进程协商（CrossProcess）

只挂 `HwlocThreadCpuAllocatorComponent` 时，同一台机器上多个 tm_kit 进程会从相同的候选顺序挑核而撞到一起。把组件换成 `HwlocCrossProcessCpuAllocatorComponent` 即开启跨进程协商：

```cpp
struct Env : ..., basic::HwlocCrossProcessCpuAllocatorComponent {};

basic::HwlocCpuAllocatorConfig cfg;
cfg.excludeCpus = {8, 9};
// cfg.crossProcessLockDir = "/dev/shm/tm_kit_cpu_locks";   // 默认值
basic::HwlocThreadCpuAllocator::configure(cfg, basic::CpuAllocatorScope::CrossProcess);
```

- **机制**：锁目录（不存在时以 `01777` 创建）中每个物理核一个 `core-<N>.lock`，N 是该核完整 cpuset 的最小 PU 号，不同 taskset/cgroup 掩码的进程得到同一个键。占用 = 对该文件持有 `flock(LOCK_EX)`；进程以任何方式退出（含 `kill -9`、崩溃）时内核释放锁，没有残留状态需要回收。已有锁文件不带 `O_CREAT` 打开，兼容 `fs.protected_regular`。`lslocks` 可直接看到持有者。
- **覆盖三种绑定方式**：`CpuAutoBind*` 跳过被其他进程占用的核；显式 `Cpus()` 和 `bindCurrentThreadTo` 碰到其他进程已占的核（含 SMT 兄弟）**一律抛 `CpuAutoBindError`**（独占），消息带锁文件中记录的最后写入者 pid（仅供诊断，可能已过期）。
- **释放**：线程租约结束或节点析构即释放该核的锁；同一核被多个显式预留引用时按引用计数。加锁中途失败（含抛异常）会回滚本次已拿到的锁。
- **excludeCpus 对其他进程也生效**：排除的核由本进程加锁“占住”，其他进程不会分配到。带 scope 的 `configure(cfg, CrossProcess)` 返回前就完成发布；要排除的核已被他人占用时抛异常并回滚配置。
- **NUMA 选择**计入其他进程的占用（读 `/proc/locks` 快照，只用于排序；真正分配以 try-lock 为准）。
- **fork**：锁 fd 带 `O_CLOEXEC`；只 fork 不 exec 的子进程在 `pthread_atfork` child 回调中关闭继承的线程/预留锁，不会延长父进程的占用（打开/登记、取消登记/关闭都与 fork 串行化）。`excludeCpus` 的锁例外：由子进程继承并保持，父进程退出后子进程的排除核仍受保护。
- 同一进程不能混用两种组件，抛 `std::logic_error`。非 Linux 平台使用 CrossProcess 抛异常。

## 最小可用示例

```cpp
using Env = infra::Environment<..., basic::HwlocCrossProcessCpuAllocatorComponent>;
using M = infra::RealTimeApp<Env>;

basic::HwlocThreadCpuAllocator::configure({}, basic::CpuAllocatorScope::CrossProcess);

auto node = M::template liftPure<int>(f, infra::LiftParameters<TP>().SuggestThreaded(true));
M::configureThreadedNode(node, infra::ThreadedNodeOptions().CpuAutoBind());

std::thread([] {
    auto lease = infra::ThreadCpuLease::bindCurrentThread<Env>("nic-rx");
    // ... 忙循环 ...
});
```

## 实时 / 回测行为差异

只影响实时模式下有专用线程的节点和用户自建线程；回测（单线程迭代）不使用分配器。

## 易错点

- 多个 tm_kit 进程同机运行时，只挂 `HwlocThreadCpuAllocatorComponent` 不会跨进程协商，忙线程可能落在同一核。
- 只有使用同一锁目录的进程之间才协商；不同容器的 `/dev/shm` 互相隔离，需挂载同一目录；不支持 NFS 等网络文件系统。
- 不用 tm_kit 的第三方进程不参与协商，仍需 `excludeCpus` 避让。能写锁目录的本机用户都能占住锁文件，目录权限由部署方负责。
- 显式绑到 `excludeCpus` 所在核、或两个显式绑定重叠，会抛异常而不是静默成功。
- `ThreadCpuLease` 的线程登记表随 fork 复制，fork 子进程应在新线程里绑核。

## 第三方依赖

[hwloc](https://www.open-mpi.org/projects/hwloc/)（vcpkg port 名 `hwloc`）。tm_basic 的 Meson feature 选项 `hwloc_cpu_allocator`（默认 `auto`）决定是否构建相关测试；`.pc` 不传递该依赖，下游使用时需自己 `dependency('hwloc')`，见 [构建](../BUILD.md)。

## 相关章节

- [实时执行器 · 自动绑核 / ThreadCpuLease](../tm_infra/10-realtime-executors.md#自动绑核cpuautobind)
- [实时执行器 · 字符串绑核策略（CpuBind）](../tm_infra/10-realtime-executors.md#字符串绑核策略cpubind)
- [Environment](../tm_infra/02-environments.md)
- [跨库模式](../PATTERNS.md)
