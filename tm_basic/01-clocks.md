---
title: 时钟组件
library: tm_basic
headers: [tm_kit/basic/real_time_clock/ClockComponent.hpp, tm_kit/basic/real_time_clock/Clock.hpp, tm_kit/basic/real_time_clock/ClockImporter.hpp, tm_kit/basic/real_time_clock/ClockOnOrderFacility.hpp, tm_kit/basic/single_pass_iteration_clock/ClockComponent.hpp, tm_kit/basic/top_down_single_pass_iteration_clock/ClockComponent.hpp, tm_kit/basic/empty_clock/ClockComponent.hpp]
keywords: [ClockComponent, real_time_clock, single_pass_iteration_clock, top_down_single_pass_iteration_clock, empty_clock, ClockImporter, ClockOnOrderFacility, 时钟, TimePoint, resolveTime, createOneShotTimer, createRecurringTimer, PreserveInputRelativeOrder, CanBeActualTimeClock, TimeComponentEnhancedWithBoostTrivialLogging, TimeComponentEnhancedWithSpdLogging]
---

# 时钟组件

## 用途

TM Kit 的时钟组件决定图中数据的**时间戳来源**与**定时器实现**。不同 App 类型使用不同的时钟命名空间，但它们对外暴露相同的接口形状，使得业务逻辑可以在不改动的情况下切换实时与回测模式。

## 头文件与命名空间

```
tm_kit/basic/real_time_clock/          — RealTimeApp 专用
tm_kit/basic/single_pass_iteration_clock/  — SinglePassIterationApp 专用
tm_kit/basic/top_down_single_pass_iteration_clock/  — TopDownSinglePassIterationApp 专用（转发）
tm_kit/basic/empty_clock/              — BasicWithTimeApp 专用
```

每个命名空间下有四个头文件：`Clock.hpp`、`ClockComponent.hpp`、`ClockImporter.hpp`、`ClockOnOrderFacility.hpp`。

## 核心类型与签名

### 1. `real_time_clock::ClockComponent`

```cpp
// tm_basic/tm_kit/basic/real_time_clock/ClockComponent.hpp:11
namespace dev::cd606::tm::basic::real_time_clock {

class ClockComponent : public Clock {
public:
    using TimePointType = std::chrono::system_clock::time_point;
    using DurationType  = std::chrono::system_clock::duration;
    static constexpr bool PreserveInputRelativeOrder = false;
    static constexpr bool CanBeActualTimeClock       = true;

    ClockComponent();
    ClockComponent(Clock::ClockSettings const &);

    TimePointType resolveTime();
    TimePointType resolveTime(TimePointType const &triggeringInputTime);

    // 返回"取消器"函数
    std::function<void()> createOneShotTimer(
        TimePointType const &fireAtTime,
        std::function<void()> callback);
    std::function<void()> createOneShotDurationTimer(
        DurationType const &fireAfterDuration,
        std::function<void()> callback);
    std::function<void()> createRecurringTimer(
        TimePointType const &firstFireAtTime,
        TimePointType const &lastFireAtTime,
        DurationType const &period,
        std::function<void()> callback);
    std::function<void()> createVariableDurationRecurringTimer(
        TimePointType const &firstFireAtTime,
        TimePointType const &lastFireAtTime,
        std::function<DurationType(TimePointType const &)> periodCalc,
        std::function<void()> callback);
};

class SimplifiedClockComponent : public Clock {
    // 与 ClockComponent 接口相同，但 resolveTime() 固定返回 TimePointType{}
    // 或直接透传 triggeringInputTime，不读取挂钟
};

}
```

`real_time_clock::ClockComponent` 的 `resolveTime()` 调用 `Clock::now()`（即挂钟）；`SimplifiedClockComponent` 的 `resolveTime(tp)` 直接透传 `tp`，适合不需要精确时间戳但仍要运行在实时模式的场景。

### 2. `single_pass_iteration_clock::ClockComponent<TimePoint>`

```cpp
// tm_basic/tm_kit/basic/single_pass_iteration_clock/ClockComponent.hpp:9
template <class TimePoint, bool AllowLocalTimeOverride = false>
class ClockComponent : public Clock<TimePoint, AllowLocalTimeOverride> {
public:
    using TimePointType = TimePoint;
    using DurationType  = decltype(TimePoint() - TimePoint());
    static constexpr bool PreserveInputRelativeOrder = true;  // 保持输入顺序
    static constexpr bool CanBeActualTimeClock       = false; // 不能成为实际时钟

    TimePointType resolveTime();
    TimePointType resolveTime(TimePointType const &triggeringInputTime);
    // resolveTime(tp) 会调用 updateLatestTime(tp) 并返回 tp
    // 即时间戳完全由输入数据驱动，不读挂钟
};
```

### 3. `top_down_single_pass_iteration_clock::ClockComponent`

```cpp
// tm_basic/tm_kit/basic/top_down_single_pass_iteration_clock/ClockComponent.hpp:9
// 是 single_pass_iteration_clock::ClockComponent 的别名
template <class TimePoint, bool AllowLocalTimeOverride = true>
using ClockComponent =
    dev::cd606::tm::basic::single_pass_iteration_clock::ClockComponent<
        TimePoint, AllowLocalTimeOverride>;
```

与 `single_pass_iteration_clock` 唯一的区别是 `AllowLocalTimeOverride` 默认值为 `true`，允许覆盖本地时间。

### 4. `empty_clock::ClockComponent<TimePoint>`

用于 `BasicWithTimeApp`，无任何定时器功能，时间戳全部来自外部注入：

```cpp
// tm_basic/tm_kit/basic/empty_clock/ClockComponent.hpp:10
template <class TimePoint>
class ClockComponent : public Clock<TimePoint> {
    static constexpr bool PreserveInputRelativeOrder = true;
    static constexpr bool CanBeActualTimeClock       = false;
};
```

### 关键 constexpr 标志含义

| 标志 | 含义 |
|---|---|
| `PreserveInputRelativeOrder` | `true` 时框架在同一时间点保持输入顺序；`false` 时不保证顺序 |
| `CanBeActualTimeClock` | `true` 表示此组件可驱动实际时间推进（实时模式用） |

## 最小可用示例

### 实时模式 Environment 配置

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40（已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,          // 不检查时间单调性
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<
        basic::real_time_clock::ClockComponent // 挂钟时间 + 日志
    >,
    // ...
>;
using M = infra::RealTimeApp<TheEnvironment>;
```

### 回测模式 Environment 配置

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:191（已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,           // 强制时间单调递增
    infra::FlagExitControlComponent,
    basic::top_down_single_pass_iteration_clock::ClockComponent<
        std::chrono::system_clock::time_point
    >,
    infra::IntIDComponent,
    // ...
>;
using M = infra::TopDownSinglePassIterationApp<TheEnvironment>;
```

### ClockImporter：定时触发的 importer

每个时钟命名空间都提供 `ClockImporter`，可产生周期性或单次触发的数据流：

```cpp
// 来源：tm_examples/clock_logic_test/ClockLogicMain.hpp（已简化）
#include <tm_kit/basic/real_time_clock/ClockImporter.hpp>

auto importer1 = basic::real_time_clock::ClockImporter<TheEnvironment>
    ::createRecurringClockImporter<std::string>(
        std::chrono::system_clock::now(),                  // 起始时间
        std::chrono::system_clock::now() + std::chrono::hours(1), // 结束时间
        std::chrono::milliseconds(1000),                   // 周期
        [](typename TheEnvironment::TimePointType const &tp) {
            // 每周期调用，返回要推入图中的值
            return std::string("tick");
        }
    );
```

## 实时 / 回测行为差异

| 维度 | `real_time_clock` | `single_pass_iteration_clock` |
|---|---|---|
| 时间戳来源 | `std::chrono::system_clock::now()`（挂钟） | 来自输入数据的时间戳，不读挂钟 |
| 定时器 | 真实 OS 定时器，异步触发 | 由框架的事件队列模拟，伪同步 |
| 线程模型 | 多线程，节点可并发运行 | 单线程，严格事件顺序 |
| `PreserveInputRelativeOrder` | `false` | `true` |
| `CanBeActualTimeClock` | `true` | `false` |
| 时间倒流 | 可能（多线程竞争） | 不会（事件队列严格排序） |

`CheckTimeComponent<true>` 在回测模式下会拒绝时间倒流的数据；实时模式通常用 `CheckTimeComponent<false>` 避免合法的微小乱序被丢弃。

## 易错点

**1. 混用 App 类型与时钟命名空间**  
`real_time_clock::ClockComponent` 放入 `TopDownSinglePassIterationApp` 的 Environment 中会导致时间戳来自挂钟，破坏回测的确定性。务必按表对应。

**2. `ClockComponent` 与 `TimeComponentEnhancedWithXxxLogging` 的组合**  
`TimeComponentEnhancedWithBoostTrivialLogging<ClockComponent>` 已经继承了 `ClockComponent`，不需要再额外放一个 `ClockComponent` 到 Environment 参数列表。重复放会导致虚继承菱形问题或编译歧义。

**3. `top_down_` 与 `single_pass_` 的时钟相同**  
两者实际上是同一个模板，仅 `AllowLocalTimeOverride` 默认值不同。若代码已用 `single_pass_iteration_clock` 命名空间，切换到 `top_down` 时需注意该标志的语义。

**4. `createRecurringTimer` 的取消器**  
返回值是一个 `std::function<void()>`，调用它可取消定时器。若不保存取消器就丢弃，定时器会永久运行直到进程退出，即使相关节点已析构。

## 第三方依赖

- `real_time_clock` 依赖 Boost.Asio 实现 OS 定时器（通过 `ClockComponentImpl`，内部使用 **`boost::asio::system_timer`**，见 `tm_basic/src/real_time_clock/ClockComponent.cpp:2` 的 include 与 `:36`、`:47`、`:62` 的三处构造）。官方文档：https://www.boost.org/doc/libs/release/doc/html/boost_asio.html

  > 是 `system_timer` 而非 `steady_timer`——前者跟随 `std::chrono::system_clock`（挂钟），后者是单调时钟。`real_time_clock::ClockComponent` 的语义是挂钟时间，所以必须用 `system_timer`。但这也意味着**系统时间被调整（NTP 校时、手动改时区）时定时器会跟着跳**。
  >
  > 该实现还为 Boost 版本做了兼容：`BOOST_VERSION >= 108700` 用 `io_context` + `make_work_guard`，更早版本用 `io_service` + `io_service::work`（`tm_basic/src/real_time_clock/ClockComponent.cpp:10`–`:27` 的三组条件编译）。

## 相关章节

- [日志组件](04-logging.md) — `TimeComponentEnhancedWithXxxLogging` 的用法
- [App 类型对照](../tm_infra/01-app-types.md) — 三种 App 的时钟要求
- [Environment 组件组合](../tm_infra/02-environments.md) — `CheckTimeComponent` 与时钟的配合
