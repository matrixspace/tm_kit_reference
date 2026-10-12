---
title: Environment 组件混合模型
library: tm_infra
headers: [tm_kit/infra/Environments.hpp]
keywords: [Environment, component, 组件, 虚继承, mixin, finalizeEnvironment, CheckTimeComponent, TrivialExitControlComponent, FlagExitControlComponent, ConstValueHolderComponent, HiddenTimeDependencyComponent, NoHiddenTimeDependencyComponent, EmptyEnvironment]
---

# Environment 组件混合模型

## 用途

`Environment` 解决的是"图里的节点怎么拿到时钟、日志、ID 生成器、网络传输"这个问题。tm_infra 自己不实现这些能力，它只定义一个**组合机制**：你把需要的 component（组件）列进模板参数，得到一个具备这些能力的 Environment 类型，然后整张图共享这一个实例。

这个机制是整个 TM Kit 实时/回测双模式的另一半支点：换掉时钟组件、换掉退出控制组件，业务代码不动，程序就从实时变成回测。

`Environments.hpp` 全文只有 **113 行**，是 tm_infra 里最短的核心头文件之一。它提供的全部内容是：一个 `Environment` 模板、五个内置组件、两个标记类、一个 `EmptyEnvironment`。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/Environments.hpp>
```

命名空间 `dev::cd606::tm::infra`。无第三方依赖，只用到 `<iostream>`、`<chrono>`、`<cstdlib>`、`<atomic>`（`tm_infra/tm_kit/infra/Environments.hpp:4`）。

## 核心类型与签名

### Environment：虚继承混合

源码注释一句话说清了设计：`//an environment is simply a mixture of components`（`tm_infra/tm_kit/infra/Environments.hpp:10`）。

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:11
template <class ... Components>
class Environment : public virtual Components... {
```

关键在 `public virtual`——**虚继承**。这是必须的：组件之间存在共同基类（比如多个时钟增强组件都继承同一个日志基类），不虚继承就会出现菱形继承的重复子对象。代价是虚继承的指针调整开销，但 Environment 全程只有一个实例，无所谓。

三个构造函数覆盖了默认构造、拷贝构造各组件、移动构造各组件：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:31
Environment() : Components()... {}
Environment(Components const &... components) : Components(components)... {}
Environment(Components &&... components) : Components(std::move(components))... {}
```

实践中最常用的是默认构造，然后对需要配置的组件单独赋值。因为是多重继承，赋值时**必须写完整的基类限定名**：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:59
env.transport::ClientSideSimpleIdentityAttacherComponent<std::string,CalculateCommand>::operator=(
    transport::ClientSideSimpleIdentityAttacherComponent<std::string,CalculateCommand>(
        "my_identity"
    )
);
```

这个 `Base::operator=(...)` 的写法看起来很怪，但在多重继承下没有更简洁的办法——`env = ...` 会试图赋值整个 Environment。同一文件 `:67` 处替换时钟组件用的也是这个写法。

有些组件提供了普通成员函数，那就直接调，不用限定名（如果没有歧义）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:55
env.transport::json_rest::JsonRESTComponent::setDocRoot(
    34567
    , "../simple_demo/plain_executables/web_enabler"
);
```

### finalizeEnvironment()：级联检测机制

这是 `Environments.hpp` 里唯一有技术含量的一段。问题是：有些组件需要在图构建完成后做一次初始化（比如启动 HTTP 服务器监听），有些不需要。`Environment` 必须对**有这个方法的组件**调用它，对**没有的组件**保持沉默——而且不能要求所有组件都提供一个空实现。

解法是经典的 SFINAE 检测 + `if constexpr` 级联：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:14
template <class X>
struct TrueType : std::true_type {};
template <class X>
static auto hasFinalizeEnvironment(int) -> TrueType<decltype(std::declval<X>().finalizeEnvironment())>;
template <class X>
static auto hasFinalizeEnvironment(long) -> std::false_type;

template <class FirstComponent, class... RemainingComponents>
void internal_finalizeEnvironment() {
    if constexpr (decltype(hasFinalizeEnvironment<FirstComponent>(0))::value) {
        this->FirstComponent::finalizeEnvironment();
    }
    if constexpr (sizeof...(RemainingComponents) > 0) {
        internal_finalizeEnvironment<RemainingComponents...>();
    }
}
```

两个重载用 `int` / `long` 参数排优先级：传字面量 `0` 时 `int` 版本优先匹配，但它的返回类型里有 `decltype(...finalizeEnvironment())`，组件没这个方法就 SFINAE 失败，回落到 `long` 版本得到 `false_type`。

然后对外暴露一个方法，按模板参数的声明顺序逐个处理：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:35
void finalizeEnvironment() {
    internal_finalizeEnvironment<Components...>();
}
```

**注意 `this->FirstComponent::finalizeEnvironment()` 的显式限定**：这一步绕过了虚函数派发，确保调到的是该组件自己的实现，而不是因名字冲突被别的组件覆盖掉。

**谁来调它？** 业务代码不用调。`AppRunner::finalize()` 内部的 `finalizeBegin()` 会调：

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData.hpp:2864
env_->EnvironmentType::finalizeEnvironment();
doTouchups();
```

顺序值得记住：先 `finalizeEnvironment()`，再 `doTouchups()`（touchup 是延迟到 finalize 阶段的图修补回调），最后才是连接完整性校验。整个流程见 [05-app-runner.md](05-app-runner.md)。

**哪些组件实现了它？** 在 tm_infra 和 tm_basic 里：没有。目前全部来自 tm_transport，且都是需要起后台服务的那几个：

- `tm_transport/tm_kit/transport/grpc_interop/GrpcInteropComponent.hpp:40`
- `tm_transport/tm_kit/transport/json_rest/JsonRESTComponent.hpp:45`
- `tm_transport/tm_kit/transport/websocket/WebSocketComponent.hpp:48`

这也解释了为什么锚点示例里 `setDocRoot` 可以在 `r.finalize()` 之前随便调——配置先存下来，真正的监听在 `finalizeEnvironment()` 里才发生。

### 内置组件

`Environments.hpp` 自带五个组件，都极小。

**`CheckTimeComponent<bool DoCheck>`** —— 纯编译期开关：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:41
template <bool DoCheck>
struct CheckTimeComponent {
    static constexpr bool CheckTime = DoCheck;
};
```

节点内部的 `TimeChecker` 读这个常量决定是否丢弃时间倒退的数据。可以在生成代码里看到它被使用：`if (StateT::CheckTime) { if (tp0_ && data.timedData.timePoint < *tp0_) { return false; } }`（`tm_infra/tm_kit/infra/RealTimeApp_TimeChecker_Piece.hpp:19`）。

注意**版本检查不受它控制**：同一段代码里 `versionChecker0_.checkVersion(...)` 在 `if (StateT::CheckTime)` 之外，无条件执行。

**`TrivialExitControlComponent`** —— `running()` 恒为 true，`exit()` 直接终止进程：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:46
struct TrivialExitControlComponent {
    static constexpr bool running() {
        return true;
    }
    static void exit(int status=0) {
        std::exit(status);
    }
};
```

两个方法都是 `static`，没有任何状态。

**`FlagExitControlComponent`** —— 用一个 atomic 标志实现可优雅退出：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:55
class FlagExitControlComponent {
private:
    std::atomic<bool> running_ = true;
public:
    bool running() const {
        return running_;
    }
    void exit(int /*status*/=0) {
        running_ = false;
    }
};
```

`exit()` 的 `status` 参数被注释掉了——这个组件不会真的退出进程，只是让主循环 `while (env->running())` 跳出。

**`ConstValueHolderComponent<T>`** —— 往 Environment 里塞一个只读的业务值：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:67
template <class T>
class ConstValueHolderComponent {
private:
    T t_;
public:
    ConstValueHolderComponent() : t_() {}
    ConstValueHolderComponent(T &&t) : t_(std::move(t)) {}
    template <class... Ts>
    ConstValueHolderComponent(Ts &&... ts) : t_(ts...) {}
    /* ... 五个默认的拷贝/移动/析构 ... */
    T const &value() const {
        return t_;
    }
};
```

用法（把一个聚合 struct 塞进去，节点内部用 `env->value()` 读）：

```cpp
// 来源：tm_examples/shared_chain_test/SharedChainTest.cpp:339（已简化）
infra::ConstValueHolderComponent<EnvValues<Chain>>
/* ... 构图前赋值 ... */
env.infra::template ConstValueHolderComponent<EnvValues<Chain>>::operator=(
    infra::ConstValueHolderComponent<EnvValues<Chain>> {chain, todayStr, dontLog}
);
```

注意那个变参构造 `template <class... Ts>` 相当贪婪，它会参与几乎所有重载决议。如果 `T` 自己有多参构造，用大括号初始化（如上例）可读性更好。

**`EmptyEnvironment<TimePoint>`** —— 不是组件，是个独立的、`final` 的最小 Environment：

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:93
template <class TimePoint=std::chrono::system_clock::time_point>
class EmptyEnvironment final {
public:
    using TimePointType = TimePoint;
    static TimePoint resolve() {
        if constexpr (std::is_same_v<TimePoint, std::chrono::system_clock::time_point>) {
            return std::chrono::system_clock::now();
        } else {
            return TimePoint {};
        }
    }
    static TimePoint resolve(TimePoint const &t) {
        return t;
    }
    static TimePoint now() {
        return resolve();
    }
};
```

源码注释说明了它的存在理由："this class is provided for template specialization purposes"（`:92`）——给那些需要一个 Environment 类型参数、但其实不需要任何能力的模板代码用。它不能作为组件混入 `Environment<...>`（`final`），也不提供日志、ID 等任何东西。`tm_examples/` 里没有它的用例。

### 两个时间依赖标记

```cpp
// 来源：tm_infra/tm_kit/infra/Environments.hpp:86
//These marks hidden/no hidden time dependency inside the environment
//Currently this affects TopDown execution scheme, but it may
//affect others in the future
class HiddenTimeDependencyComponent {}; //this used to need to be put into environment to turn on hidden dependency for top-down, but now turning on is default, so this has no effect
class NoHiddenTimeDependencyComponent {}; //this now needs to be put into environment to turn off hidden dependency for top-down.
```

两个空类，纯标记用。源码注释交代了历史变迁，这段必须读懂：

- **`HiddenTimeDependencyComponent` 现已无效**。它曾经用来**打开**隐藏时间依赖，但现在打开是默认行为，所以放进 Environment 不起任何作用。遇到老代码里有它，可以安全删掉。
- **`NoHiddenTimeDependencyComponent` 用来关闭**它。这是现在唯一有效的那个。

"隐藏时间依赖"指什么：图里两个节点之间可能存在不体现在连边上的时间先后关系（典型情形就是上文提到的 `markStateSharing`——两个节点共享状态，谁先跑结果不同）。`TopDownSinglePassIterationApp` 默认采用一种保守的执行策略来尊重这种依赖：

```cpp
// 来源：tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:84
static constexpr bool UseExecutionStrategyThatAllowsForHiddenTimeDependency
    = !std::is_convertible_v<
        StateT *
        , NoHiddenTimeDependencyComponent *
    >;
```

这个常量在 `runOneStep()`（`tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:3052`）里选择两条执行分支：

| | 默认（允许隐藏时间依赖） | 放了 `NoHiddenTimeDependencyComponent` |
|---|---|---|
| 每步从任务队列取多少 | **一个**（`taskQueue_.top()` 后立刻 `pop` 并执行） | 一批（同一 importer 的连续任务一次跑完，遇到不同 importer 才 break） |
| 全局时间顺序 | 严格 | 仅保证 importer 内部有序 |
| 速度 | 慢 | 快 |
| 适用 | 有状态共享、结果对执行顺序敏感 | 各 importer 分支相互独立 |

**建议**：回测结果要与实时结果对齐，就用默认（什么都不放）。只有在确认图里没有隐藏依赖、且回测速度成为瓶颈时，才考虑加 `NoHiddenTimeDependencyComponent`。`tm_examples/` 里没有用它的例子，说明默认行为是常态。

此外源码里还能看到一个相关的标记 `DontForceDrainTopDownSinglePassImporter`（定义在 `tm_infra/tm_kit/infra/TopDownSinglePassIterationApp.hpp:28`，使用在 `:3061`），它控制每步是否把 importer 抽干，不在 `Environments.hpp` 里定义，本篇不展开。

## 最小可用示例：实时 vs 回测的 Environment 对照

锚点是 `tm_examples/simple_demo/plain_executables/MainLogic.cpp`——同一文件里两套 Environment，业务逻辑 `MainLogicCombination` 完全复用。

**实时**（`run_real_or_virtual`，`:39`）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::real_time_clock::ClockComponent>,
    transport::BoostUUIDComponent,
    transport::ClientSideSimpleIdentityAttacherComponent<std::string,CalculateCommand>,
    transport::ServerSideSimpleIdentityCheckerComponent<std::string,ConfigureCommandPOCO>,
    transport::ServerSideSimpleIdentityCheckerComponent<std::string,ClearCommands>,
    transport::AllNetworkTransportComponents,
    transport::HeartbeatAndAlertComponent
>;
using M = infra::RealTimeApp<TheEnvironment>;
```

**回测**（`run_backtest`，`:190`）：

```cpp
// 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:191
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::FlagExitControlComponent,
    basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::top_down_single_pass_iteration_clock::ClockComponent<std::chrono::system_clock::time_point,true>,false>,
    basic::IntIDComponent<>
>;
using M = infra::TopDownSinglePassIterationApp<TheEnvironment>;
```

### 逐项对照

| 组件槽位 | 实时 | 回测 | 为什么不同 |
|---|---|---|---|
| 时间检查 | `CheckTimeComponent<false>` | `CheckTimeComponent<true>` | 实时数据来自网络，轻微乱序是常态，开检查会丢数据；回测数据应严格有序，开检查能暴露数据问题 |
| 退出控制 | `TrivialExitControlComponent` | `FlagExitControlComponent` | 回测的 `finalize()` 内有 `while (env->running())` 主循环，需要一个能翻成 false 的标志才能收尾；实时的 `finalize()` 立即返回，不需要 |
| 时钟 | `real_time_clock::ClockComponent` | `top_down_single_pass_iteration_clock::ClockComponent<..., true>` | 挂钟 vs 数据时间戳。时钟组件的 `PreserveInputRelativeOrder` 必须与 app type 匹配，否则编译失败 |
| 日志增强的第二参数 | 省略（默认） | `false` | 控制日志是否带实时时间戳；回测里时间是虚拟的，打真实时间戳会造成误解 |
| ID 生成 | `transport::BoostUUIDComponent` | `basic::IntIDComponent<>` | 实时需要跨进程全局唯一的 UUID；回测单进程内递增整数就够，且可复现 |
| 身份校验 | 三个 identity 组件 | 无 | 回测不跨进程，没有调用方身份这回事 |
| 网络传输 | `AllNetworkTransportComponents` | 无 | 回测的数据来自文件 importer，不碰网络 |
| 心跳告警 | `HeartbeatAndAlertComponent` | 无 | 同上 |

**可复用的关键**：业务逻辑只依赖这些组件提供的**接口**（`env->now()`、`env->log(...)`、`env->new_id()`），不依赖具体实现。所以 `MainLogicCombination` 两边都能编过。

另一组更简洁的对照在 `tm_examples/clock_logic_test/main.cpp`，四种模式各一套 Environment（`:24`、`:70`、`:95`、`:118`），差异只在时钟组件与退出控制上，适合作为模板抄。

## 实时 / 回测行为差异

`Environments.hpp` 本身的代码**在两种模式下行为完全一致**——它只是个组合机制，不含任何与时间相关的逻辑。差异全部来自你**往里放什么组件**，即上一节的对照表。

唯一的例外是 `NoHiddenTimeDependencyComponent`：它只对 `TopDownSinglePassIterationApp` 有效（源码注释：`Currently this affects TopDown execution scheme, but it may affect others in the future`，`:87`），放进实时模式的 Environment 里不起作用，但也不报错——这是个容易埋坑的地方。

## 易错点

- **忘了虚继承的后果**：如果你自己写组件并让它继承某个基类，必须保证整条继承链都是虚继承，否则混入 `Environment` 时会出现重复子对象，表现是"明明设置了却读不到"。
- **赋值必须写完整基类限定名**：`env = ...` 不行，`env.SomeComponent::operator=(...)` 才行。见上文示例。
- **组件声明顺序影响 `finalizeEnvironment()` 的调用顺序**：`internal_finalizeEnvironment<Components...>()` 严格按模板参数顺序级联（`:36`）。如果两个组件的 finalize 有先后依赖（A 必须先起来 B 才能连上去），顺序就是语义的一部分。实践中应尽量避免这种依赖。
- **`HiddenTimeDependencyComponent` 是个陷阱**：名字看着像在打开功能，实际什么都不做。要关闭请用 `NoHiddenTimeDependencyComponent`。
- **时钟与 app type 不匹配会编译失败**，报错是 SFINAE 失败（"没有匹配的模板"），不直观。先检查 `PreserveInputRelativeOrder` 是否对，详见 [01-app-types.md](01-app-types.md)。
- **`CheckTimeComponent<false>` 不会关掉版本检查**：两者是独立机制，见上文。
- **`EmptyEnvironment` 不能当组件用**，它是 `final` 的。
- **在 `r.finalize()` 之前完成所有组件配置**：`finalizeEnvironment()` 在 `finalize()` 内部被调用（`WithTimeData.hpp:2864`），之后再改组件配置，像 `setDocRoot` 这类"配置先存、finalize 时生效"的组件就不会读到新值了。

## 第三方依赖

`Environments.hpp` 本身无第三方依赖，只用标准库。

但实用的 Environment 基本都要混入外部库的组件：

- `basic::TimeComponentEnhancedWithBoostTrivialLogging` → [Boost.Log](https://www.boost.org/doc/libs/release/libs/log/) 的 trivial logging
- `basic::TimeComponentEnhancedWithSpdLogging` → [spdlog](https://github.com/gabime/spdlog)
- `transport::BoostUUIDComponent` → [Boost.Uuid](https://www.boost.org/doc/libs/release/libs/uuid/)
- `transport::CrossGuidComponent` → [crossguid](https://github.com/graeme-hill/crossguid)

这些都在 tm_basic / tm_transport 里，不是 tm_infra 的依赖。

## 相关章节

- [00-overview.md](00-overview.md) —— tm_infra 总览
- [01-app-types.md](01-app-types.md) —— 四种执行模式，以及 `PreserveInputRelativeOrder` 约束
- [05-app-runner.md](05-app-runner.md) —— `finalize()` 全流程与 touchup
- [07-time-and-data.md](07-time-and-data.md) —— 时间检查与版本检查
- [08-runners-and-control.md](08-runners-and-control.md) —— `terminationController` 与退出控制组件的配合
- [../tm_basic/01-clocks.md](../tm_basic/01-clocks.md) —— 四套时钟组件
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
