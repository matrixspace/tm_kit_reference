---
title: DeclarativeGraph — 声明式图构建
library: tm_infra
headers: [tm_kit/infra/DeclarativeGraph.hpp, tm_kit/infra/AutoConnectionSubGraph.hpp, tm_kit/infra/GenericLift.hpp]
keywords: [DeclarativeGraph, DeclarativeGraphChain, AutoConnectionSubGraph, GenericComponentLiftAndRegistration, 声明式, 图构建, 注册, 连接, dynamicConnect, dynamicPlaceOrder]
---

# DeclarativeGraph — 声明式图构建

## 用途

`DeclarativeGraph<R>` 提供一种声明式语法，把节点的**注册**与**连接**合并到一个初始化列表中完成，避免分散在代码各处的 `r.registerXxx` / `r.connect` 调用。它是 `AppRunner` 命令式 API 的替代写法，不改变运行语义。

`AutoConnectionSubGraph<R>` 是更激进的自动连线变体：只注册节点，框架按类型相容性自动连接，适合小型内部子图。

## 头文件与命名空间

```cpp
#include <tm_kit/infra/DeclarativeGraph.hpp>
#include <tm_kit/infra/AutoConnectionSubGraph.hpp>

namespace dev::cd606::tm::infra
```

## 核心类型与签名

### DeclarativeGraph

```cpp
// tm_infra/tm_kit/infra/DeclarativeGraph.hpp:14
template <class R>
class DeclarativeGraph {
public:
    DeclarativeGraph(
        std::string const &prefix,
        std::vector<OneDeclarativeGraphItem<R>> const &items
    );
    void operator()(R &r, std::string const &outerPrefix = "") const;
};
```

构造后得到一个可调用对象，调用 `dg(r)` 即把所有节点注册到 runner `r` 并完成连接。`prefix` 会前缀到所有节点名称，便于把一组节点归入同一命名作用域。

### DeclarativeGraphChain

```cpp
// tm_infra/tm_kit/infra/DeclarativeGraph.hpp:23
struct DeclarativeGraphChain {
    DeclarativeGraphChain(std::vector<std::string> const &nodes);
};
```

表示一条线性连接链：`{"A", "B", "C"}` 等价于 `A → B → C`，在初始化列表中作为独立的 `OneDeclarativeGraphItem`。

### OneDeclarativeGraphItem — 支持的构造形式

`OneDeclarativeGraphItem<R>` 是初始化列表中的每一项，有多种构造方式（`tm_infra/tm_kit/infra/DeclarativeGraph.hpp`）：

| 构造参数 | 含义 |
|---|---|
| `(name, f)` | 用 `GenericLift` 提升 `f` 并按类型注册（importer/action/exporter/facility） |
| `(name, LiftAsMulti{}, f)` | 同上，但强制提升为 multi-action |
| `(name, LiftAsFacility{}, f)` | 强制提升为 on-order facility |
| `(name, DelayImporter<T>{}, f)` | 注册为延迟触发的 importer |
| `(name, LazyImporter<T>{}, f)` | 注册为惰性 importer |
| `(name, CurtailAction{}, f)` | 注册为 curtailed action |
| `(name, shared_ptr<T>)` | 注册已有节点对象 |
| `(name, VacuousImporterItem<A>{})` | 注册空白 importer（永不产出） |
| `(name, TrivialExporterItem<A>{})` | 注册丢弃 exporter |
| `(name, PassThroughActionItem<A>{})` | 注册直通 action |
| `DeclarativeGraphChain{{"A","B","C"}}` | 线性链连接 |
| `(source, sink)` | 单条连接（两字符串） |
| `(sourceName, sourceIdx, sink)` | 多输出节点的第 `sourceIdx` 个输出连接到 `sink` |
| `(source, sinkName, sinkIdx)` | 连接到多输入节点的第 `sinkIdx` 个输入 |
| `(sourceName, sourceIdx, sinkName, sinkIdx)` | 带端口索引的双向连接 |
| `(source, facility, sink)` | `placeOrder`：把 source 接到 facility，响应输出到 sink |
| `(source, facility, std::monostate{})` | `placeOrderAndForget`：不关心响应 |

行号参考：单条连接约第 202 行，facility 连接约第 250 行（`tm_infra/tm_kit/infra/DeclarativeGraph.hpp`）。

### AutoConnectionSubGraph

```cpp
// tm_infra/tm_kit/infra/AutoConnectionSubGraph.hpp:165
template <class R>
class AutoConnectionSubGraph {
public:
    AutoConnectionSubGraph(
        R &r,
        std::vector<OneAutoConnectionItem<R>> const &items
    );
};
```

与 `DeclarativeGraph` 相似，但不需要声明连接——框架按类型自动匹配 source 与 sink。额外支持直接传入 `R::Source<A>` 或 `R::Sink<A>` 句柄，以及 `FacilitioidConnector<A,B>` 进行全局自动接入。

## 最小可用示例

### 示例 1：线性链 + 循环图（DeliberateCycleTest）

```cpp
// 来源：tm_examples/common_flow_util_tests/DeliberateCycleTest.cpp:35
infra::DeclarativeGraph<R>("", {
    // 注册节点（名称 + lambda，自动提升）
    {"importer", M::constFirstPushImporter<double>(0.0)}
    , {"action", [](double x) -> std::optional<double> {
        return (x < 100.0) ? std::optional<double>{x + 1.0} : std::nullopt;
    }}
    , {"delayer", basic::CommonFlowUtilComponents<M>::delayer<double>(
        std::chrono::milliseconds(100)
    )}
    , {"exporter", [&env](double x) {
        env.log(infra::LogLevel::Info, std::to_string(x));
    }}
    // 连接：线性链
    , infra::DeclarativeGraphChain {{"importer", "action", "exporter"}}
    // 形成环
    , {"action", "delayer"}
    , {"delayer", "action"}
})(r);
```

### 示例 2：facility 连接（ClockLogicMain）

```cpp
// 来源：tm_examples/clock_logic_test/ClockLogicMain.hpp:74（已简化）
infra::DeclarativeGraph<R>("", {
    // 注册节点
    {"recurring",    importer1}
    , {"converter",  infra::withtime_utils::keyify<std::string, typename M::EnvironmentType>}
    , {"genKey",     [](std::string &&s) -> typename M::template Key<std::string> {
                         return M::keyify(std::move(s));
                     }}
    , {"print",      [](typename M::template InnerData<std::string> &&s) { /* ... */ }}
    , {"fileSink",   fileSink}
    , {"serialize",  serialize}
    , {"addTopic",   addTopic}
    , {"facility",   facility}
    , {"clockFacilityOutput", [](typename M::template KeyedData<std::string,std::string> &&s2)
                                 -> std::string { return s2.key.key() + " --- " + s2.data; }}
    , {"print2",     [](typename M::template InnerData<
                           typename M::template KeyedData<std::string,std::string>> &&s)
                     { /* ... */ }}
    // 连接
    , infra::DeclarativeGraphChain {{"recurring", "addTopic", "serialize", "fileSink"}}
    , {"recurring", "print"}
    // facility 连接：source → facility → sink
    , {"oneShot1", "converter"}, {"converter", "facility", "print2"}
    , {"oneShot2", "facility"}
    , {"recurring", "genKey"}
    , {"clockFacilityOutput", "print"}
})(r);
```

### 示例 3：线性管道（KUSeqTest）

```cpp
// 来源：tm_examples/common_flow_util_tests/KUSeqTest.cpp:42
infra::DeclarativeGraph<R>("", {
    {"imp",      /* importer */ }
    , {"step1",  /* action  */ }
    , {"step2",  /* action  */ }
    , {"step3",  /* action  */ }
    , {"step4",  /* action  */ }
    , {"exporter", /* exporter */}
    , infra::DeclarativeGraphChain {{"imp", "step1", "step2", "step3", "step4", "exporter"}}
})(r);
```

## 实时 / 回测行为差异

`DeclarativeGraph` 本身不含任何运行时逻辑，只是 `AppRunner` 注册与 `dynamicConnect` / `dynamicPlaceOrder` 的语法糖。实时与回测的差异完全由被注册节点的行为决定，与写法无关。

`AutoConnectionSubGraph` 同理，自动匹配仍基于 `AppRunner` 的类型系统，两种模式下行为一致。

## 易错点

**1. prefix 叠加**  
`DeclarativeGraph("subgraph", {...})(r)` 会把所有节点名变为 `subgraph/<name>`。若后续用 `r.template sourceByName<T>("name")` 查找，需加上前缀：`r.template sourceByName<T>("subgraph/name")`。

**2. 连接必须在同一 DeclarativeGraph 或在节点注册后**  
`DeclarativeGraph` 内部按顺序执行注册，再执行连接项，因此连接可以写在节点注册之后，也可以混排——两步都在 `operator()` 调用时才真正执行。但若连接项里的节点名在本批次之外，需确保它们已在外部用 `r.registerXxx` 注册。

**3. 类型推导失败**  
`(name, f)` 形式依赖 `GenericLift` 推导函数类型：纯返回值 → action 或 exporter；返回 `void` → exporter；参数为 `InnerData` 且无返回值 → exporter（kleisli 形态）。重载函数或成员函数指针可能导致推导失败，此时改用 `shared_ptr` 形式或先创建节点再传入。

**4. facility 三元组写法顺序**  
三字符串构造 `(source, facility, sink)` 触发 `dynamicPlaceOrder`；两字符串 `(source, sink)` 触发 `dynamicConnect`。名字写错顺序会导致连接类型错误，编译通过但运行时行为异常。

**5. AutoConnectionSubGraph 的类型冲突**  
自动连接按数据类型匹配：若多个节点输出同一类型 `T`，框架会把所有输出都连到所有接受 `T` 的输入，产生广播。这在意图上是单对单连接时是 BUG，此时应改用 `DeclarativeGraph` 的显式连接。

## 相关章节

- [AppRunner 连接与命名](05-app-runner.md)
- [GenericLift 与节点提升](03-nodes-and-lifting.md)
- [on-order facility 四种变体](04-facilities.md)
