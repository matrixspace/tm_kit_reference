---
title: 日志组件
library: tm_basic
headers: [tm_kit/basic/LoggingComponentBase.hpp, tm_kit/basic/SpdLoggingComponent.hpp, tm_kit/basic/TrivialBoostLoggingComponent.hpp]
keywords: [LoggingComponentBase, SpdLoggingComponent, TrivialBoostLoggingComponent, TimeComponentEnhancedWithSpdLogging, TimeComponentEnhancedWithBoostTrivialLogging, spdlog, LogLevel, setLogFilePrefix, log, 日志, 日志组件]
---

# 日志组件

## 用途

`tm_basic` 提供两套日志实现，均继承自 `LoggingComponentBase`，通过 `env.log(level, message)` 接口写入日志。两套实现都可以独立使用，也可以通过 `TimeComponentEnhancedWithXxxLogging<ClockComponent>` 的形式与时钟组件合并，这是量化程序最常见的配置方式。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/LoggingComponentBase.hpp>
#include <tm_kit/basic/SpdLoggingComponent.hpp>
#include <tm_kit/basic/TrivialBoostLoggingComponent.hpp>

namespace dev::cd606::tm::basic
```

## 核心类型与签名

### LoggingComponentBase

```cpp
// tm_basic/tm_kit/basic/LoggingComponentBase.hpp:7
class LoggingComponentBase {
public:
    virtual ~LoggingComponentBase() {}
    virtual void logThroughLoggingComponentBase(
        dev::cd606::tm::infra::LogLevel l,
        std::string const &s
    ) = 0;
};
```

日志组件的抽象基类。`Environment` 通过虚继承持有它，框架内部通过 `dynamic_cast` 调用 `logThroughLoggingComponentBase` 写日志。

### TrivialBoostLoggingComponent

```cpp
// tm_basic/tm_kit/basic/TrivialBoostLoggingComponent.hpp:24
struct TrivialBoostLoggingComponent : public virtual LoggingComponentBase {
    static void log(infra::LogLevel l, std::string const &s);
    virtual void logThroughLoggingComponentBase(
        infra::LogLevel l, std::string const &s) override;
};
```

基于 Boost.Log 的极简实现，直接写到 stdout/stderr，无文件轮换，无格式配置。适合调试和回测（不需要保留日志文件的场景）。

### TimeComponentEnhancedWithBoostTrivialLogging

```cpp
// tm_basic/tm_kit/basic/TrivialBoostLoggingComponent.hpp:56
template <class TimeComponent,
          bool LogThreadID         = true,
          bool ForceActualTimeLogging = false>
class TimeComponentEnhancedWithBoostTrivialLogging
    : public TimeComponent, public virtual LoggingComponentBase
{
public:
    // 设置日志文件前缀（不设则输出到控制台）
    void setLogFilePrefix(
        std::string const &prefix,
        bool containTimePart = false,
        std::optional<uintmax_t> maxSize = std::nullopt
    );

    void log(infra::LogLevel l, std::string const &s);

    virtual void logThroughLoggingComponentBase(
        infra::LogLevel l, std::string const &s) override;
};
```

把时钟组件与 Boost.Log 合并。`TimeComponent` 通常是 `real_time_clock::ClockComponent` 或 `top_down_single_pass_iteration_clock::ClockComponent<T>`。

- `LogThreadID = true`：日志行包含线程 ID
- `ForceActualTimeLogging = true`：回测模式下强制用挂钟时间（而非虚拟时间）写时间戳

### SpdLoggingComponent

```cpp
// tm_basic/tm_kit/basic/SpdLoggingComponent.hpp:34
class SpdLoggingComponent : public virtual LoggingComponentBase {
    // spdlog 的独立日志组件，不含时钟
    virtual void logThroughLoggingComponentBase(
        infra::LogLevel l, std::string const &s) override;
};
```

### TimeComponentEnhancedWithSpdLogging

```cpp
// tm_basic/tm_kit/basic/SpdLoggingComponent.hpp:212
template <class TimeComponent,
          bool LogThreadID             = true,
          bool ForceActualTimeLogging  = false,
          typename TimeZone = dev::cd606::tm::basic::time_zone_spec::Local>
class TimeComponentEnhancedWithSpdLogging
    : public TimeComponent, public virtual LoggingComponentBase
{
public:
    TimeComponentEnhancedWithSpdLogging();

    // 配置日志文件（可选异步写入）
    void setLogFilePrefix(
        std::string const &prefix,
        bool containTimePart = false,
        std::optional<uintmax_t> maxSize = std::nullopt,
        std::optional<SpdLoggingAsyncParameter> asyncParam = std::nullopt
    );

    void log(infra::LogLevel l, std::string const &s);
};
```

基于 spdlog 的实现，支持异步日志、文件轮换、时区配置，生产环境推荐使用。

#### SpdLoggingAsyncParameter

```cpp
// tm_basic/tm_kit/basic/SpdLoggingComponent.hpp:204
struct SpdLoggingAsyncParameter {
    bool useAsync;
    std::size_t queueSize;
};
inline constexpr auto defaultSpdLoggingAsyncParameter =
    SpdLoggingAsyncParameter { true, spdlog::details::default_async_q_size };
```

## 最小可用示例

### 实时模式：TimeComponentEnhancedWithBoostTrivialLogging

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40（已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<
        basic::real_time_clock::ClockComponent
    >
    // 其他组件...
>;

int main() {
    TheEnvironment env;
    env.log(infra::LogLevel::Info, "程序启动");
    // 或在节点 lambda 中：
    // s.environment->log(infra::LogLevel::Info, "数据: " + ...);
}
```

### 回测模式：单独 TrivialBoostLoggingComponent

```cpp
// 来源：tm_examples/db_one_list_subscription（多处，已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::FlagExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<
        basic::top_down_single_pass_iteration_clock::ClockComponent<
            std::chrono::system_clock::time_point
        >
    >,
    infra::IntIDComponent
>;
```

### 写日志到文件

```cpp
TheEnvironment env;
// 输出到 ./my_log_20241001_120000.log（含时间部分）
env.setLogFilePrefix("my_log", true);
// 输出到 ./my_log.log（固定文件名）
env.setLogFilePrefix("my_log", false);
// 限制文件大小（字节）
env.setLogFilePrefix("my_log", true, std::optional<uintmax_t>(50*1024*1024));
```

### 节点内写日志

```cpp
// 在 InnerData 形态的 lambda 内（kleisli 形态）
{"print", [](typename M::template InnerData<std::string> &&s) {
    std::ostringstream oss;
    oss << s.timedData;
    s.environment->log(infra::LogLevel::Info, oss.str());
}}

// 在闭包捕获 env 的 exporter 内
{"exporter", [&env](double x) {
    env.log(infra::LogLevel::Info, std::to_string(x));
}}
```

来源：`tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:48`，`tm_examples/clock_logic_test/ClockLogicMain.hpp:80`。

## 实时 / 回测行为差异

| 维度 | 实时模式 | 回测模式 |
|---|---|---|
| 日志时间戳来源 | 挂钟（`resolveTime()` 读 `now()`） | 虚拟时间（数据驱动） |
| `ForceActualTimeLogging=true` | 无意义（本来就是挂钟） | 强制用挂钟写时间戳，不随虚拟时间走 |
| 异步日志 | 推荐开启（减少 I/O 影响延迟） | 通常不需要，单线程 I/O 即可 |
| 文件轮换 | 生产环境设置 `maxSize` | 回测通常写单文件或不写文件 |

## 易错点

**1. `TimeComponentEnhancedWithXxx` 已包含时钟，不要重复放**  
`TimeComponentEnhancedWithBoostTrivialLogging<ClockComponent>` 继承了 `ClockComponent`，Environment 参数列表中不需要再单独放一个 `ClockComponent`。重复会导致虚继承歧义或编译错误。

**2. `setLogFilePrefix` 必须在 `r.finalize()` 之前调用**  
日志文件在首次 `log()` 时初始化。若在 `finalize()` 之后调用 `setLogFilePrefix`，部分早期日志可能已写到控制台。

**3. 回测下的异步日志有丢失风险**  
`TopDownSinglePassIterationApp` 是单线程且快速结束的。若开启 spdlog 异步模式，进程退出时异步队列未必全部落盘。回测场景建议用同步模式或 `TrivialBoostLoggingComponent`。

**4. 节点内 lambda 使用 `s.environment->log` vs. 闭包捕获 `env`**  
在 `InnerData` 形态（kleisli）的 lambda 中，`s.environment` 是正确的环境指针。在普通 action lambda（接受值类型）中无法直接访问 env，需要闭包捕获 `&env`。两者混用会导致空指针或捕获了错误的 env。

## 第三方依赖

- **Boost.Log** — TrivialBoostLoggingComponent 使用。官方文档：https://www.boost.org/doc/libs/release/libs/log/doc/html/index.html
- **spdlog** — SpdLoggingComponent 使用。官方文档：https://github.com/gabime/spdlog，API 文档：https://spdlog.docsforge.com/

## 相关章节

- [时钟组件](01-clocks.md) — `TimeComponentEnhancedWithXxx` 的时钟参数
- [LogLevel 枚举](../tm_infra/08-runners-and-control.md) — `infra::LogLevel` 定义
- [Environment 组件组合](../tm_infra/02-environments.md) — 虚继承混入机制
