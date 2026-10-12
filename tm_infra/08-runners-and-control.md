---
title: SynchronousRunner、TerminationController 与运行控制
library: tm_infra
headers: [tm_kit/infra/SynchronousRunner.hpp, tm_kit/infra/TerminationController.hpp, tm_kit/infra/ControllableNode.hpp, tm_kit/infra/ObservableNode.hpp, tm_kit/infra/LogLevel.hpp]
keywords: [SynchronousRunner, TerminationController, RunForever, TerminateAtTimePoint, TerminateAfterDuration, ImmediatelyTerminate, IControllableNode, IObservableNode, terminationController, LogLevel, 同步运行, 停止控制]
---

# SynchronousRunner、TerminationController 与运行控制

## 用途

本篇涵盖图运行的**停止控制**与**同步（非事件循环）调用**两个主题：

- `TerminationController` / `terminationController` — 控制 `r.finalize()` 之后主线程的等待与退出方式。
- `SynchronousRunner<M>` — 不组装完整图，而是直接对 importer 或 facility **同步调用**一次，取回结果后返回；适合测试、脚本、命令行工具。
- `IControllableNode` / `IObservableNode` — 节点可选实现的接口，用于在运行时通过状态对象控制或观察节点行为。
- `LogLevel` — 贯穿全框架的日志级别枚举。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/TerminationController.hpp>
#include <tm_kit/infra/SynchronousRunner.hpp>
#include <tm_kit/infra/ControllableNode.hpp>
#include <tm_kit/infra/ObservableNode.hpp>
#include <tm_kit/infra/LogLevel.hpp>

namespace dev::cd606::tm::infra
```

---

## TerminationController

### 用途

`terminationController` 是一个模板函数，接受一个"控制对象"，**在其析构时阻塞或立即返回**，从而控制进程在 `r.finalize()` 后何时退出。这是 TM Kit 程序结束逻辑的统一入口。

### 核心类型

```cpp
// tm_infra/tm_kit/infra/TerminationController.hpp:8

// 在指定时间点退出
class TerminateAtTimePoint {
public:
    TerminateAtTimePoint(std::chrono::time_point<std::chrono::system_clock> tp);
    ~TerminateAtTimePoint(); // 阻塞到 tp，然后析构返回
};

// 在指定时长后退出
class TerminateAfterDuration {
public:
    TerminateAfterDuration(std::chrono::system_clock::duration duration);
    ~TerminateAfterDuration(); // 阻塞 duration，然后析构返回
};

// 立即退出（不阻塞）
class ImmediatelyTerminate {};

// 永久运行，直到 runningCheck() 返回 false
class RunForever {
public:
    // 带自定义检查函数
    RunForever(
        std::function<bool()> const &runningCheck = []() { return true; },
        std::chrono::system_clock::duration duration = std::chrono::seconds(100)
    );
    // 绑定到 Environment 的 running() 方法
    template <class Env>
    RunForever(Env *env,
               std::chrono::system_clock::duration duration = std::chrono::seconds(100));
    ~RunForever(); // 轮询 runningCheck()，每次间隔 duration
};

// 通用入口：对象析构即触发逻辑
template <class T>
inline void terminationController(T const &) {}
```

`terminationController` 本身是空函数，仅触发参数对象构造和析构时的 RAII 阻塞逻辑。

### 最小可用示例

```cpp
// 来源：tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:56
r.finalize();
infra::terminationController(infra::RunForever {});

// 来源：tm_examples/clock_logic_test/main.cpp:61
r.finalize();
infra::terminationController(infra::TerminateAtTimePoint {
    std::chrono::system_clock::now() + std::chrono::seconds(5)
});

// 来源：tm_examples/clock_logic_test/timeout_test.cpp:67
infra::terminationController(infra::TerminateAfterDuration {
    std::chrono::seconds(3)
});

// 来源：tm_examples/clock_logic_test/main.cpp:89
infra::terminationController(infra::ImmediatelyTerminate {});

// 绑定 Environment 的 running() 检查（FlagExitControlComponent）
// 来源：tm_examples/db_one_list_subscription/DBOneListSinglePassPrinter.cpp:134
infra::terminationController(infra::RunForever {&env});
```

### 实时 / 回测行为差异

| 场景 | 推荐用法 |
|---|---|
| 实时模式长驻进程 | `RunForever {&env}` — 绑定 `FlagExitControlComponent::running()` |
| 实时模式定时结束 | `TerminateAtTimePoint` / `TerminateAfterDuration` |
| 回测（TopDown 单遍） | `ImmediatelyTerminate {}` — 图跑完自然结束 |
| 单遍迭代含限时逻辑 | `TerminateAfterDuration` |

回测模式下图完成后 `r.finalize()` 会自行返回，`ImmediatelyTerminate` 确保不阻塞。

### 易错点

`RunForever` 的 `duration` 参数是**轮询间隔**，不是超时。若 `runningCheck()` 始终返回 `true`（例如没有绑定 `FlagExitControlComponent`），进程将永不退出。生产代码中务必绑定 `env` 或显式设置退出条件。

---

## SynchronousRunner

### 用途

`SynchronousRunner<M>` 是 `AppRunner<M>` 的**同步调用变体**：它不构建完整的事件循环图，而是：
- 对 importer 同步运行一次，返回所有产出数据
- 对 facility 同步提交请求，等待并返回响应

典型用途：命令行脚本、单元测试、数据库批量导入/导出。

### 核心类型与签名

```cpp
// tm_infra/tm_kit/infra/SynchronousRunner.hpp:16
template <class M>
class SynchronousRunner {
public:
    using AppType = M;
    using EnvironmentType = typename M::EnvironmentType;

    SynchronousRunner(typename M::EnvironmentType *env);

    typename M::EnvironmentType *environment() const;

    // 运行 importer，收集所有产出
    template <class T>
    std::unique_ptr<typename M::template SynchronousRunResult<T>>
    importItem(
        std::shared_ptr<typename M::template Importer<T>> const &importer
    );

    // 运行 importer，直到 condition 返回 true
    template <class T, class Condition>
    std::unique_ptr<typename M::template SynchronousRunResult<T>>
    importItemUntil(
        std::shared_ptr<typename M::template Importer<T>> const &importer,
        Condition const &condition
    );

    // 向 facility 提交一个请求，等待响应
    template <class T1, class T2>
    std::unique_ptr<typename M::template SynchronousRunResult<
        typename M::template KeyedData<T1,T2>>>
    placeOrderWithFacility(
        typename M::template InnerData<typename M::template Key<T1>> &&key,
        std::shared_ptr<typename M::template OnOrderFacility<T1,T2>> const &facility
    );
    // 重载：接受 InnerData<T1>（自动 keyify）
    // 重载：接受 T1 &&（自动 pureInnerData + keyify）

    // 流式调用 facility（多次提交，合并结果）
    template <class T1, class T2>
    class SynchronousFacilityStreamer { ... };
};
```

`SynchronousRunResult<T>` 是一个包含多个 `TimedDataWithEnvironment<T>` 的容器，可迭代：

```cpp
auto result = sr.importItem(importer);
for (auto &item : *result) {
    // item 是 TimedDataWithEnvironment<T>
    auto &value = item.timedData.value;
}
```

### 最小可用示例

```cpp
// 来源：tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:30
using SR = infra::SynchronousRunner<M>;

Env env;
SR sr(&env);

// 同步运行 importer，等待所有数据
auto importer = transport::db_table_importer_exporter::DBTableImporterFactory<M>
    ::createImporter<test_data>(session, "test_table");

auto result = sr.importItem(importer);
for (auto const &item : *result) {
    std::cout << item.timedData.value << '\n';
}
```

```cpp
// 来源：tm_examples/csv_test/CsvTest.cpp:121（已简化）
using M = infra::TopDownSinglePassIterationApp<BasicEnvironment>;
using SR = infra::SynchronousRunner<M>;

BasicEnvironment env;
SR sr(&env);

// 直接向 facility 提交请求
auto facility = ...; // 构造 facility
auto result = sr.placeOrderWithFacility(
    M::keyify(MyRequest { ... }),
    facility
);
// result 含有一条或多条 KeyedData<MyRequest, MyResponse>
```

### 实时 / 回测行为差异

| 维度 | RealTimeApp + SynchronousRunner | TopDownSinglePassIterationApp + SynchronousRunner |
|---|---|---|
| 线程模型 | 在调用线程同步运行，importer 内部仍可能启动短暂线程 | 完全单线程，确定性 |
| 时间 | 使用挂钟时间 | 使用虚拟时间（由环境驱动） |
| 典型用途 | 实时工具脚本、一次性查询 | 回测数据读取、单元测试 |

### 易错点

**1. importer 只能启动一次**  
同一个 importer `shared_ptr` 传给 `importItem` 两次会抛出 `std::runtime_error("SynchronousRunner::importItem: importer previously started")`。每次调用需新建 importer 实例，或使用 `importItemUntil` 配合条件重用。

**2. facility 的 `IExternalComponent`**  
若 facility 实现了 `IExternalComponent`（需要 `start(env)` 初始化），`SynchronousRunner` 会在第一次 `placeOrderWithFacility` 时自动调用 `start`，此后复用。同一 facility 多次调用是安全的。

**3. SynchronousRunResult 的迭代**  
结果集在 importer 产出 final-flagged 数据时结束收集。若 importer 永不发出 final flag（如持续推送型 importer），`importItem` 将永久阻塞。

---

## IControllableNode 与 IObservableNode

### 用途

这两个接口允许节点在运行时被外部**控制**（修改内部状态）或**观察**（读取内部状态），无需停止图。

```cpp
// tm_infra/tm_kit/infra/ControllableNode.hpp:9
template <class StateT>
class IControllableNode {
public:
    virtual ~IControllableNode() = default;
    // 子类实现具体的控制接口
};

// tm_infra/tm_kit/infra/ObservableNode.hpp:9
template <class StateT>
class IObservableNode {
public:
    virtual ~IObservableNode() = default;
    // 子类实现具体的观察接口
};
```

`RealTimeApp` 在 `TwoWayHolder` 和 `OneWayHolder` 中通过 `dynamic_cast` 检测节点是否实现了这两个接口（见 `tm_infra/tm_kit/infra/RealTimeApp.hpp:766`），并把接口指针暴露给框架。

实际场景中，自定义节点可继承这两个接口，实现类似"动态调参"或"实时状态监控"的功能。`tm_basic` 的某些组件（如 `GraphControlFacility`）正是通过这一机制实现图的在线控制。

---

## LogLevel

### 核心类型

```cpp
// tm_infra/tm_kit/infra/LogLevel.hpp:10
namespace dev::cd606::tm::infra {
    enum class LogLevel {
        Trace,
        Debug,
        Info,
        Warning,
        Error,
        Critical
    };

    std::string logLevelToString(LogLevel l);
    bool logLevelFromString(std::string_view const &s, LogLevel &l);
    std::ostream &operator<<(std::ostream &os, LogLevel l);

    // 便捷辅助，根据 level 调用 env.log()
    template <class Env, class T>
    inline void simpleLog(Env &env, LogLevel level, T const &t);
}
```

`Environment` 的日志组件（如 `TrivialBoostLogging`、`SpdLogging`）均以 `LogLevel` 作为级别参数。框架内部（action 核心、importer 等）也在调试路径上使用 `LogLevel::Debug`。

### 用法示例

```cpp
// 来源：tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:48
env.log(infra::LogLevel::Info, std::to_string(x));

// 来源：tm_examples/db_one_list_subscription（多处）
env.log(infra::LogLevel::Error, "connection failed");
```

---

## 实时 / 回测行为差异（汇总）

| 功能 | 实时模式 | 回测（TopDown 单遍） |
|---|---|---|
| `terminationController` | `RunForever` / `TerminateAt*` | `ImmediatelyTerminate` 或不调用 |
| `SynchronousRunner` | 支持，但 importer 可能使用真实 I/O | 完全确定性，无外部 I/O |
| `IControllableNode` | 实时调参有意义 | 单遍运行中动态调参意义有限 |
| `LogLevel` | 两种模式一致，由绑定的日志组件决定输出目标 | 同左 |

---

## 相关章节

- [Environment 组件组合模型](02-environments.md) — `FlagExitControlComponent` 与 `TrivialExitControlComponent`
- [AppRunner 连接与命名](05-app-runner.md) — `r.finalize()` 的调用时机
- [App 类型对照](01-app-types.md) — 三种 App 的线程模型
