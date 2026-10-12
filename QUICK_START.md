---
title: 快速上手
library: meta
headers: []
keywords: [quick start, 快速上手, 第一个程序, 最小骨架, Environment, AppRunner, RealTimeApp, SinglePassIterationApp, 实时回测双模, MainLogicCombination, 构建]
---

# 快速上手

从零写一个 TM Kit 程序。目标读者是已经会 C++17、但第一次接触本框架的开发者。

**前置**：仓库已按 [BUILD.md](BUILD.md) 构建并安装（`tm_infra` → `tm_basic` → `tm_transport`），`PKG_CONFIG_PATH` 里能找到 `tm_kit_*` 的 `.pc` 文件。

## 1. 三个概念

TM Kit 程序 = **一个 Environment** + **一张图** + **一个 AppRunner**。

| 概念 | 是什么 | 类比 |
|---|---|---|
| **Environment** | 若干 component 的虚继承混合体，承载时钟、日志、ID 生成、传输能力 | 依赖注入容器 |
| **图（graph）** | 节点（importer / action / exporter / facility）与连边 | 数据流水线 |
| **AppRunner** | 注册节点、连接、校验、启动图的对象 | 图的 builder + executor |
| **App 类型（`M`）** | `RealTimeApp` 或 `SinglePassIterationApp`，决定图的执行语义 | 运行时模式 |

**核心约束**：节点定义用 `M::template liftPure<T>` 这类形式，`M` 是模板参数。换 `M` 就换了执行模式，**业务代码不变**。这是实时/回测双模的全部秘密。

## 2. 最小程序：单文件三种模式

以 `tm_examples` 的 `Env` 类型为例（来源：`tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp` 各 `main` 分支的组织方式）：

```cpp
#include <tm_kit/infra/Environments.hpp>
#include <tm_kit/infra/RealTimeApp.hpp>
#include <tm_kit/infra/SinglePassIterationApp.hpp>
#include <tm_kit/infra/TerminationController.hpp>
#include <tm_kit/basic/real_time_clock/ClockComponent.hpp>
#include <tm_kit/basic/single_pass_iteration_clock/ClockComponent.hpp>
#include <tm_kit/basic/SpdLoggingComponent.hpp>
#include <tm_kit/basic/CommonFlowUtils.hpp>
#include <tm_kit/transport/BoostUUIDComponent.hpp>

using namespace dev::cd606::tm;

// ---- 1) 实时模式的 Environment ----
using RealTimeEnv = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::BoostUUIDComponent
>;

// ---- 2) 回测模式的 Environment（只换时钟组件）----
using BacktestEnv = infra::Environment<
    infra::CheckTimeComponent<true>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<
        basic::single_pass_iteration_clock::ClockComponent<std::chrono::system_clock::time_point>
    >,
    transport::BoostUUIDComponent
>;

// ---- 3) 业务逻辑：对 M 模板化，两种模式共用 ----
template <class R>
void businessLogic(R &r) {
    using M = typename R::AppType;
    using CFU = basic::CommonFlowUtilComponents<M>;

    // 产生数据：1 到 100
    auto importer = M::template constFirstPushImporter<int>(42);

    // 变换：+1
    auto addOne = M::template liftPure<int>([](int &&x) { return x + 1; });

    // 消费：打印
    auto printer = M::template pureExporter<int>(
        [](int &&x) {
            std::cout << "value = " << x << std::endl;
        }
    );

    r.exportItem("printer", printer, r.execute("addOne", addOne, r.importItem("source", importer)));
}

int main(int argc, char **argv) {
    bool isRealTime = (argc > 1 && std::string_view(argv[1]) == "realtime");

    if (isRealTime) {
        RealTimeEnv env;
        using M = infra::RealTimeApp<RealTimeEnv>;
        infra::AppRunner<M> r(&env);
        businessLogic(r);
        r.finalize();          // 启动各节点线程后立即返回
        infra::terminationController(infra::TerminateAfterDuration(std::chrono::seconds(2)));
    } else {
        BacktestEnv env;
        env.setLocalTime(std::chrono::system_clock::now());   // 回测必须设置起始时间
        using M = infra::SinglePassIterationApp<BacktestEnv>;
        infra::AppRunner<M> r(&env);
        businessLogic(r);
        r.finalize();          // 单遍迭代：finalize 内部就把整遍跑完
    }
    return 0;
}
```

**这个骨架的要点**：

- `businessLogic<R>` 只依赖 `R`，不依赖任何具体 Environment
- **实时与回测的驱动语义完全不同**（下面说的都是 App 层的行为；`AppRunner::finalize()` 只是先校验图再 `m_.finalize()(env_)` 调过去）：
  - `RealTimeApp`：`finalize()` 启动各节点的后台线程后**立即返回**，图靠 `terminationController` 维持运行
  - `SinglePassIterationApp`：`finalize()` **内部就执行完整的单遍迭代循环**（`WithTimeData.hpp:2980` 的 `m_.finalize()(env_)`），直到 `finalFlag` 或环境退出为止——**没有 `r.run()` 这样的方法**
- `env.setLocalTime(...)` 是回测的必需步骤——单遍迭代时钟需要起始时间

> `AppRunner` 没有独立的头文件。它定义在 `tm_infra/tm_kit/infra/WithTimeData.hpp:629`，随 `RealTimeApp.hpp` / `SinglePassIterationApp.hpp` 一起被引入。

## 3. 三种 App 类型怎么选

| App 类型 | 何时用 | 执行方式 | 时钟组件 |
|---|---|---|---|
| `RealTimeApp<Env>` | 实盘、行情接入、服务端 | 多线程；`finalize()` 启动线程后返回，靠 `terminationController` 维持 | `basic::real_time_clock::ClockComponent` |
| `SinglePassIterationApp<Env>` | **回测（推荐）**、批处理 | 单线程；`finalize()` **内部跑完整遍迭代** | `basic::single_pass_iteration_clock::ClockComponent` |
| `TopDownSinglePassIterationApp<Env>` | 回测（需要 top-down 数据请求语义） | 单线程，自顶向下驱动 | 同上 |
| `BasicWithTimeApp<Env>` | 不使用 framework 时钟，纯 CPU 流处理 | 同步 | 无 |

默认选 `SinglePassIterationApp` 做回测。详见 [tm_infra/01-app-types](tm_infra/01-app-types.md)。

## 4. Environment 里放什么

Environment 是 `/` 分隔的能力清单。最小可用集：

```cpp
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,          // 是否校验时间单调（实时=false，回测=true）
    infra::TrivialExitControlComponent,        // 退出控制
    basic::TimeComponentEnhancedWithSpdLogging<   // 时钟 + 日志
        basic::real_time_clock::ClockComponent
    >,
    transport::BoostUUIDComponent              // Key<T> 的 ID 生成
>;
```

按需追加：

| 需要什么 | 加什么组件 | 文档 |
|---|---|---|
| 网络传输 | `transport::zeromq::ZeroMQComponent` 等（或 `transport::AllNetworkTransportComponents`） | [tm_transport/00](tm_transport/00-overview.md) |
| 心跳与服务发现 | `transport::HeartbeatAndAlertComponent` | [tm_transport/05](tm_transport/05-heartbeat-and-alert.md) |
| 共享链 | `transport::AllChainComponents` | [tm_transport/04](tm_transport/04-shared-chains.md) |
| 事务键值存储 | `basic::transaction::v2` 相关的 `DSComponent`/`THComponent` | [tm_basic/09](tm_basic/09-transaction.md) |
| 身份校验 | `transport::SimpleIdentityCheckerComponent` 等 | [tm_transport/06](tm_transport/06-security.md) |
| 跨进程 UUID | `transport::CrossGuidComponent` | [tm_transport/00](tm_transport/00-overview.md) |

**注意**：组件是有顺序的虚继承混合，同名组件只能出现一次。`CheckTimeComponent<true>` 与 `<false>` 是不同类型，不要混用。

## 5. 图的构建：三种写法

### 5.1 命令式（最直白）

```cpp
auto importer = /* ... */;
auto action   = /* ... */;
auto exporter = /* ... */;

r.registerImporter("source", importer);
r.registerAction("step", action);
r.registerExporter("sink", exporter);

r.connect(r.importItem(importer), r.actionAsSink(action));
r.connect(r.actionAsSource(action), r.exporterAsSink(exporter));
r.finalize();
```

### 5.2 链式（`execute` 嵌套，推荐）

```cpp
r.exportItem("sink", exporter,
    r.execute("step", action,
        r.importItem("source", importer)));
r.finalize();
```

### 5.3 声明式（`DeclarativeGraph`，最简洁）

来源：`tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:55–62`

```cpp
infra::DeclarativeGraph<R>("", {
    {"importer", someImporter}
    , {"dispatch", basic::CommonFlowUtilComponents<M>::dispatchOneByOne<test_data>()}
    , {"print", [&env](test_data &&x) { /* ... */ }}
    , infra::DeclarativeGraphChain({"importer", "dispatch", "print"})
})(r);
r.finalize();
```

详见 [tm_infra/06-declarative-graph](tm_infra/06-declarative-graph.md)。

## 6. 实时 / 回测双模的标准架构

**把业务逻辑抽到独立的组合模板中**，两种模式各自注入依赖。这是 `tm_examples/simple_demo/` 的组织方式。

```
项目/
├── app_combination/
│   ├── MainLogicCombination.hpp    # 业务组合：template <class R, class ...Deps>
│   └── MockCalculatorCombination.hpp  # 回测用的本地 mock
├── plain_executables/
│   ├── DataSource.cpp              # 实时：发布端
│   └── MainLogic.cpp               # 实时/回测：同一文件，运行时分支
└── program_logic/
    └── MainLogic.hpp               # 业务逻辑本体
```

关键模式（来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:101–116`）：

```cpp
R::FacilitioidConnector<CalculateCommand, CalculateResult> calc;
if (isReal) {
    // 实时：网络设施 + 心跳服务发现
    calc = transport::MultiTransportRemoteFacilityManagingUtils<R>
        ::setupOneNonDistinguishedRemoteFacility<CalculateCommand, CalculateResult>(
            r, heartbeatSource.clone()
            , std::regex("simple_demo plain Calculator")
            , "calculator facility"
        ).facility;
} else {
    // 回测：本地 mock，类型完全相同
    calc = &(MockCalculatorCombination<R, basic::real_time_clock::ClockOnOrderFacility<TheEnvironment>>::service);
}

// 下游代码一字不改
MainLogicInput<R> input { calc, /* ... */ };
auto output = MainLogicCombination(r, env, std::move(input), logicChoice, "alert.topic");
```

**核心**：`calc` 的类型在两种模式下**完全一致**（`FacilitioidConnector<A,B>`），因此 `MainLogicCombination` 不需要知道自己在哪种模式下跑。

## 7. 数据进出：importer 与 exporter

| 数据源/去向 | 用什么 |
|---|---|
| 内存常量 / 一次性推送 | `M::constFirstPushImporter<T>(value)`、`M::triggerImporter<T>()` |
| 周期性时钟 | `basic::AppClockHelper<M>::Importer::createRecurringClockImporter<T>(...)` |
| CSV / HDF5 / FlatPack | `StructFieldInfoBasedCsvImporterFactory<M,T>::createImporter(...)` |
| 文件字节流录制/重放 | `basic::ByteDataWithTopicRecordFileImporterExporter<M>` |
| 网络广播 | `MultiTransportBroadcastListenerManagingUtils<R>::oneBroadcastListener<T>(...)` |
| 网络发布 | `MultiTransportBroadcastPublisherManagingUtils<R>::oneBroadcastPublisher<T>(...)` |
| 数据库表 | `DBTableImporterFactory<M>::createImporter<T>(session, table)` |
| 共享链 | `SharedChainCreator<M>::readerFactory<...>(...)` |

详见 [tm_infra/03-nodes-and-lifting](tm_infra/03-nodes-and-lifting.md)、[tm_basic/07](tm_basic/07-csv-hdf5-flatpack.md)、[tm_transport/01](tm_transport/01-broadcast.md)。

## 8. 构建你的项目

在 `meson.build` 中通过 pkg-config 引入：

```meson
project('my_tm_app', 'cpp', default_options: ['cpp_std=c++17'])

if get_option('buildtype') == 'debug'
    tm_infra_dep = dependency('tm_kit_infra_debug')
    tm_basic_dep = dependency('tm_kit_basic_debug')
    tm_transport_dep = dependency('tm_kit_transport_debug')
else
    tm_infra_dep = dependency('tm_kit_infra')
    tm_basic_dep = dependency('tm_kit_basic')
    tm_transport_dep = dependency('tm_kit_transport')
endif

executable('my_app', 'main.cpp',
    dependencies: [tm_infra_dep, tm_basic_dep, tm_transport_dep])
```

配置：

```bash
source ./build-env-setting-rocky.sh     # 必须先 source，PKG_CONFIG_PATH 在里面设置
cd my_project
meson setup builddir --buildtype=debug \
  --prefix=/data1/dev/rockylinux8.6/tm_kit \
  --cmake-prefix-path=/data1/dev/rockylinux8.6/vcpkg/installed/x64-linux
ninja -j4 -C builddir                   # -j4 是系统资源约束，不是建议
```

调试 `.pc` 解析问题：

```bash
pkg-config --exists tm_kit_basic_debug && echo found
pkg-config --cflags tm_kit_basic_debug
pkg-config --libs   tm_kit_basic_debug | tr ' ' '\n' | head -20
```

## 9. 常见起步错误

**1. 忘了 `source build-env-setting-rocky.sh`**  
`PKG_CONFIG_PATH` 未设置 → `dependency('tm_kit_basic')` 失败。`build.sh` 刻意不设工具链，环境必须自己 source。

**2. 回测模式忘了 `env.setLocalTime(...)`**  
`single_pass_iteration_clock::ClockComponent` 需要起始时间。不设置会得到未定义的时间戳或直接失败。

**3. 以为回测要手动调用 `r.run()`**  
没有这个方法。`SinglePassIterationApp` 的迭代循环在 `AppRunner::finalize()` 内部执行（`WithTimeData.hpp:2980`：`m_.finalize()(env_)`，而单遍迭代 App 的 `finalize()` 返回的正是一个 `while (env->running())` 循环）。多图交错跑才需要额外调用——那用 `MultiAppRunnerUtilComponents::run(r1, r2)`（见 [tm_basic/10](tm_basic/10-app-runner-utils.md)）。

**4. 认为"回测就是把时钟调快"**  
TM Kit 的回测是**单遍迭代**（数据驱动），不是虚拟时钟加速。区别在于：虚拟时钟下节点仍是异步多线程的；单遍迭代下所有节点在单线程里按数据顺序推进，因此**结果完全确定**。

**5. 节点类型与连边不匹配**  
`r.connect(source, sink)` 要求类型严格一致。`Action<int,int>` 的输出只能接 `Sink<int>`。多个输入要显式用 `std::variant` 建模（见 [tm_infra/00](tm_infra/00-overview.md)）。

**6. 在 `finalize()` 之后注册节点**  
`finalize()` 做图校验与 touchup。之后注册的节点不参与校验。用 `r.registerTouchUp` 处理需要在 finalize 阶段补的边。

**7. 把传输节点用在回测 App 里**  
`MultiTransportBroadcastListener` 等硬编码 `RealTimeApp`，放进 `SinglePassIterationApp` 会得到一堆模板错误。回测改用文件 importer 或本地 mock。

## 10. 下一步

| 想做 | 看 |
|---|---|
| 理解数据流图模型 | [tm_infra/00-overview](tm_infra/00-overview.md) |
| 选 App 类型 | [tm_infra/01-app-types](tm_infra/01-app-types.md) |
| 写节点（lift 函数族） | [tm_infra/03-nodes-and-lifting](tm_infra/03-nodes-and-lifting.md) |
| 用 facility 做请求-响应 | [tm_infra/04-facilities](tm_infra/04-facilities.md) |
| 跨进程通信 | [tm_transport/00-overview](tm_transport/00-overview.md) |
| 事务型状态服务 | [tm_basic/09-transaction](tm_basic/09-transaction.md) |
| 事件溯源 | [tm_basic/08-shared-chain](tm_basic/08-shared-chain.md) + [tm_transport/04](tm_transport/04-shared-chains.md) |
| 跨库易错点汇总 | [PATTERNS](PATTERNS.md) |
| 找示例 | [EXAMPLES_MAP](EXAMPLES_MAP.md) |
