---
title: 机器生成的代码片段与数字后缀约定
library: tm_infra
headers: [tm_kit/infra/RealTimeApp_PureN_Piece.hpp, tm_kit/infra/RealTimeApp_EnhancedMaybeN_Piece.hpp, tm_kit/infra/RealTimeApp_ConnectN_Piece.hpp, tm_kit/infra/RealTimeApp_VariantSink_Piece.hpp, tm_kit/infra/RealTimeApp_Merge_Piece.hpp, tm_kit/infra/WithTimeData_ConnectN_ClassPiece.hpp, tm_kit/infra/WithTimeData_VariantSink_ClassPiece.hpp]
keywords: [Piece, ClassPiece, 生成代码, 元数, arity, liftPure2, enhancedMaybe2, actionAsSink_2_0, connect_2_0, merge2, 数字后缀, ActionCore, ProducerN, TimeChecker, VariantSink]
---

# 机器生成的代码片段与数字后缀约定

## 用途

`tm_infra/tm_kit/infra/` 下有 **52 个机器生成的文件**，合计约 **14 万行**，占了整个库 16.9 万行的八成以上。它们存在的唯一理由是：C++17 没有足够的手段把"对 2 到 20 路输入分别展开"写成一份优雅的变参模板，于是作者选择用代码生成器把每个元数（arity）都铺开。

**你不需要读这些文件。** 本篇要回答的只有三个问题：

1. 为什么 API 名字里有数字（`liftPure2`、`actionAsSink_2_0`）？
2. 数字到底怎么数？
3. 上限是多少？

读完这三点，你就能正确使用这些 API，而不必打开任何一个生成文件。

## 文件命名规律

统一格式是：

```
<App>_<Feature>_Piece.hpp
```

`<App>` 只有五种取值，前四个是执行模式（见 [01-app-types.md](01-app-types.md)），第五个是数据与图核心：

| `<App>` | 片段数 | 宿主头文件 |
|---|---|---|
| `RealTimeApp` | 17 | `RealTimeApp.hpp` |
| `TopDownSinglePassIterationApp` | 16 | `TopDownSinglePassIterationApp.hpp` |
| `SinglePassIterationApp` | 8 | `SinglePassIterationApp.hpp` |
| `BasicWithTimeApp` | 5 | `BasicWithTimeApp.hpp` |
| `WithTimeData` | 6 | `WithTimeData.hpp` |

另有两个变体后缀 `_ClassPiece.hpp`（只在 `WithTimeData` 下，共 2 个），区别见下文。

## 这些文件不是头文件

**最重要的一条**：`*_Piece.hpp` 不是独立的头文件，而是被 `#include` 到**类体内部**的代码片段。它们没有 include guard，没有 `#include` 任何东西，没有命名空间声明，文件第一行就直接是 `template <class A0, class A1>` 或者 `private:`。

证据：`RealTimeApp_Merge_Piece.hpp` 的第 1 行是 `private:`，最后一行是一个成员函数的 `}`。单独编译它必然失败。

它们在宿主类体内被 include，例如：

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp.hpp:2116
#include <tm_kit/infra/RealTimeApp_Merge_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_PureN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_MaybeN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_EnhancedMaybeN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_KleisliN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_MultiN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_EnhancedMultiN_Piece.hpp>
#include <tm_kit/infra/RealTimeApp_KleisliMultiN_Piece.hpp>
```

这解释了几件事：

- 为什么 `liftPure2` 是 `RealTimeApp` 的**静态成员函数**，而文件里看不到任何 `class RealTimeApp`——它被 include 进了类体。
- 为什么片段里能直接用 `StateT`、`TimePoint`、`InnerData<T>`、`Action<A,B>` 这些名字而不加限定——它们是宿主类的作用域内的名字。
- 为什么在 IDE 里跳转到 `liftPure2` 的定义会落到一个"看起来语法错误"的文件里。这是正常的。
- 为什么一次改动会导致大面积重编译。

`RealTimeApp.hpp` 里共有 17 处这样的 include，分布在 `:113` 到 `:3400`；`TopDownSinglePassIterationApp.hpp` 有 16 处（`:183` 到 `:3049`）；`WithTimeData.hpp` 有 6 处（`:430` 到 `:3645`）。

## 元数族清单

按"生成什么"分，一共这些族。下表的"元数范围"列用 `grep` 实测而非估计。

### 对外 API 族（你会直接调用的）

| 族 | 典型名字 | 元数范围 | 实测依据 |
|---|---|---|---|
| PureN | `liftPure2` … `liftPure20` | 2–20 | `RealTimeApp_PureN_Piece.hpp:21` 起，最大 `liftPure20` |
| MaybeN | `liftMaybe2` … `liftMaybe20` | 2–20 | `RealTimeApp_MaybeN_Piece.hpp` |
| EnhancedMaybeN | `enhancedMaybe2` … `enhancedMaybe20` | 2–20 | `RealTimeApp_EnhancedMaybeN_Piece.hpp:25` 起 |
| MultiN | `liftMulti2` … `liftMulti20` | 2–20 | `RealTimeApp_MultiN_Piece.hpp` |
| EnhancedMultiN | `enhancedMulti2` … `enhancedMulti20` | 2–20 | `RealTimeApp_EnhancedMultiN_Piece.hpp` |
| KleisliN | `kleisli2` … `kleisli20` | 2–20 | `RealTimeApp_KleisliN_Piece.hpp` |
| KleisliMultiN | `kleisliMulti2` … `kleisliMulti20` | 2–20 | `RealTimeApp_KleisliMultiN_Piece.hpp` |
| Merge | `merge2` … `merge20` | 2–20 | `RealTimeApp_Merge_Piece.hpp`，最大 `MergeT20` / `Merge20` / `merge20` |
| VariantSink | `actionAsSink_2_0` … `actionAsSink_20_19` | N: 2–20, K: 0–(N-1) | `RealTimeApp_VariantSink_Piece.hpp:2` 起 |
| ConnectN | `connect_2_0` … `connect_20_19` | N: 2–20, K: 0–(N-1) | `RealTimeApp_ConnectN_Piece.hpp:2` 起 |
| ExecuteAction | `execute(...)` 的重载，无数字后缀 | variant 2–20 路 | `RealTimeApp_ExecuteAction_Piece.hpp:1` 起 |

**pure / maybe / multi / kleisli / enhanced 这几个词的含义**不在本篇范围，见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md) 与 [../GLOSSARY.md](../GLOSSARY.md)。本篇只管数字。

### 内部实现族（你不会直接用，但报错信息里会出现）

| 族 | 生成内容 | variant 路数上限 |
|---|---|---|
| ActionCore | `ActionCore<std::variant<A0,...>, B, ...>` 的偏特化 | 20（`A0`–`A19`） |
| MultiActionCore | 同上，multi 输出版 | 20 |
| AbstractAction / AbstractActionCore | 抽象基类的偏特化 | 20 |
| ProducerN | `Producer<std::variant<A0,...>>`，含 `addHandler_0` … `addHandler_K` | 20 |
| TimeChecker | `TimeChecker<bool, std::variant<A0,...>>`，每路一个时间戳 + 一个 version checker | 20 |
| ThreadedHandler | 实时模式下的线程化分发（仅 `RealTimeApp`） | 20 |
| Provider_Adapter | `ProviderAdapter_N_K`，把多路 provider 适配成单路（仅 `SinglePassIterationApp`） | N: 2–20 |
| TupleCopy | `makeCopy` / `ValueCopier<std::tuple<...>>`（仅 `WithTimeData`） | 20 |
| VariantExecute | `AppRunner::execute` 的多路重载（仅 `WithTimeData`） | 20 |

**结论：所有族的元数上限都是 20。** 需要超过 20 路输入时没有生成好的代码可用，得自己把若干路先合成一个 struct 再传。实践中 20 路已经很夸张了。

### 两个 ClassPiece

`_ClassPiece.hpp` 与 `_Piece.hpp` 的区别是：前者生成**按 `<N, K>` 索引的类模板特化**，后者生成**带数字后缀的函数**。

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData_VariantSink_ClassPiece.hpp:1
template <std::size_t N, std::size_t K>
class ActionAsSink {};
template <>
class ActionAsSink<1, 0> {
```

```cpp
// 来源：tm_infra/tm_kit/infra/WithTimeData_ConnectN_ClassPiece.hpp:1
template <std::size_t N, std::size_t K>
class Connect {};
template <std::size_t N, std::size_t K>
class ConnectAny {};
template <>
class Connect<1, 0> {
```

为什么需要这个形式：当 N 和 K 本身是模板参数（编译期算出来的值）时，你没法拼出 `actionAsSink_2_0` 这样的函数名——C++ 没有标识符拼接。`ActionAsSink<N, K>` 则可以直接用变量。`DeclarativeGraph` 内部正是靠它把 `{"t2v", 0, "printer1"}` 这种写法翻译成具体连接的（见 [06-declarative-graph.md](06-declarative-graph.md)）。

注意这两个 ClassPiece 的特化**从 `<1, 0>` 开始**，而函数形式从 `_2_0` 开始——因为 N=1 的情形在函数形式下就是不带后缀的 `actionAsSink` / `connect`。

## 数字怎么数

这是本篇的核心。规则只有两条。

### 规则一：单个数字 = 输入路数 N

`liftPure2`、`enhancedMaybe2`、`merge2`、`kleisli2` 里的数字是**这个节点接受几路输入**。它直接对应内部的 variant 路数：

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp_EnhancedMaybeN_Piece.hpp:25
template <class A0, class A1, class F>
static auto enhancedMaybe2(F &&f, LiftParameters<TimePoint> const &liftParam = LiftParameters<TimePoint>()) -> std::shared_ptr<Action<std::variant<A0,A1>,typename decltype(f(std::move(*((std::tuple<TimePoint, std::variant<A0,A1>> *) nullptr))))::value_type>>
```

看返回类型里的 `Action<std::variant<A0,A1>, ...>`：`2` 个显式模板参数 `A0,A1`，组成 `std::variant<A0,A1>`。**N 个数字 ⇒ N 个显式模板参数 ⇒ N 路 variant。**

`liftPure2` 同理：

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp_PureN_Piece.hpp:21
static auto liftPure2(F &&f, LiftParameters<TimePoint> const &liftParam = LiftParameters<TimePoint>()) -> std::shared_ptr<Action<std::variant<A0,A1>,decltype(f(std::move(*((std::variant<A0,A1> *) nullptr))))>>
```

**N=1 时不带后缀**：`liftPure`（`RealTimeApp_PureN_Piece.hpp:668`）、`liftMaybe`（`RealTimeApp_MaybeN_Piece.hpp:763`）。所以后缀序列是「无后缀, 2, 3, …, 20」，没有 `liftPure1`。

### 规则二：两个数字 = `_<N>_<K>`，N 是总路数，K 是第几路（0 起）

`actionAsSink_2_0` 读作"这个 action 一共 2 路输入，我要拿第 0 路的 sink"：

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp_VariantSink_Piece.hpp:2
template <class A0, class A1, class B>
Sink<A0> actionAsSink_2_0(Action<std::variant<A0,A1>,B> &action) {
```

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp_VariantSink_Piece.hpp:6
template <class A0, class A1, class B>
Sink<A1> actionAsSink_2_1(Action<std::variant<A0,A1>,B> &action) {
```

对比这两个签名就一目了然：N 固定是 2（决定了 `Action<std::variant<A0,A1>,B>`），K 决定返回的是 `Sink<A0>` 还是 `Sink<A1>`。

`connect_2_0` 是同一套规则，只是方向相反——它接受一个多路 source 并连到单路 sink：

```cpp
// 来源：tm_infra/tm_kit/infra/RealTimeApp_ConnectN_Piece.hpp:2
void connect_2_0(Source<std::variant<A0,A1>> &&source, Sink<A0> const &sink) {
```

**K 的取值范围是 `0` 到 `N-1`**，所以 N=2 只有 `_2_0` 和 `_2_1`，不存在 `_2_2`。

### 一句话记法

> 单数字 = 有几路；双数字 = 共几路 _ 第几路（从 0 数）。

## 最小可用示例

锚点是 `tm_examples/simple_demo/app_combination/MainLogicCombination.hpp`，一个文件里把两条规则都用到了。

**规则一，`enhancedMaybe2`：**

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:61
auto logic = M::template enhancedMaybe2<
        simple_demo::InputData
      , simple_demo::CalculateResult
    >(
        boost::hana::curry<2>(std::mem_fn(&MainLogic::runLogic))(mainLogicPtr.get())
      , dev::cd606::tm::infra::LiftParameters<std::chrono::system_clock::time_point>()
            .DelaySimulator(
                [](int which, std::chrono::system_clock::time_point const &) -> std::chrono::system_clock::duration {
                    if (which == 0) {
                        return std::chrono::milliseconds(100);
                    } else {
                        return std::chrono::milliseconds(0);
                    }
                }
            )
    );
```

被 lift 的函数签名必须与 `2` 对得上：

```cpp
// 来源：tm_examples/simple_demo/program_logic/MainLogic.hpp:24
std::optional<simple_demo::CalculateCommand> runLogic(
    std::tuple<std::chrono::system_clock::time_point, std::variant<simple_demo::InputData, simple_demo::CalculateResult>> &&input
);
```

三处数字必须一致：`enhancedMaybe2` 的 `2`、显式模板参数的个数（`InputData`, `CalculateResult`）、函数参数里 variant 的路数。

顺手注意 `DelaySimulator` 的回调第一个参数叫 `which`——它就是 K，即"这次来的是第几路输入"，`0` 对应 `InputData`。这是 K 这个索引在业务代码里露面的地方。`LiftParameters` 的定义见 `tm_infra/tm_kit/infra/WithTimeData.hpp:49`。

**规则二，`actionAsSink_2_0`：**

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:139
return MainLogicOutput<R> {
    r.actionAsSink_2_0(logic)
};
```

`logic` 就是上面那个 `enhancedMaybe2` 的产物。`_2_0` 表示"logic 有 2 路输入，这里取第 0 路（`InputData`）的 sink 交给外部去接数据源"。第 1 路（`CalculateResult`）在同一文件 `:92` 处被回环接上，这正是 facility 允许成环的用法。

**对比：单路输入不带后缀**（同一文件 `:97`）：

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:94
input.commandConnector(
    r,
    r.execute("keyify", keyify, std::move(cmd)),
    r.actionAsSink(extractResult)
);
```

`extractResult` 是 `liftPure`（无后缀，单输入）产生的，所以取 sink 也用无后缀的 `actionAsSink`。

**其他族的真实用例：**

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:208
auto logic = M::template liftMaybe2<
        double
      , simple_demo::CalculateResult
    >(
        boost::hana::curry<2>(std::mem_fn(&MainLogic2::runLogic))(mainLogicPtr.get())
        /* ... LiftParameters 略 ... */
    );
```

```cpp
// 来源：tm_examples/transport_utils/relayer.cpp:103
auto perClockUpdate = M::kleisli2<basic::VoidStruct,uint64_t>(
```

```cpp
// 来源：tm_examples/transport_utils/historical_republisher.cpp:295
auto replayRunner = App::liftPure2<ReplayParameter, std::chrono::system_clock::time_point>(&runReplay, infra::LiftParameters<App::TimePoint>().RequireMask(infra::FanInParamMask("11")).FireOnceOnly(true));
```

最后这一行里的 `RequireMask(infra::FanInParamMask("11"))` 值得注意：字符串 `"11"` 的长度正好是 N=2，每一位对应一路输入，表示"两路都必须到齐才触发"。这与 `merge2` 的 `std::bitset<2> requireMask` 参数（`RealTimeApp_Merge_Piece.hpp:36`）是同一个概念。**但 `RequireMask` 与 `FanInParamMask` 在当前仓库的 tm_infra / tm_basic / tm_transport 源码中都搜不到定义**，这一行应是对应了本仓库之外或更新版本的 API，照抄会编译失败——存疑，见文末。

## 怎么正确使用这些 API

一个实用的工作流程：

1. **先确定输入路数 N**。数清这个节点要从几个不同的上游收数据。
2. **选族**。按输出语义选 pure / maybe / multi，按是否需要时间戳选 enhanced，按是否要自己控制输出时间选 kleisli。见 [03-nodes-and-lifting.md](03-nodes-and-lifting.md)。
3. **拼名字**：`<族名><N>`，N=1 则省略数字。
4. **写函数**：参数类型是 `std::variant<A0,...,A(N-1)> &&`（enhanced 系列则是 `std::tuple<TimePoint, std::variant<...>> &&`）。
5. **取 sink 接上游**：`r.actionAsSink_<N>_<K>(node)`，K 从 0 数。N 路就要接 N 次，**一路都不能漏**——`AppRunner` 在 `finalize()` 时会检查每个参数位是否都被连接，没连上会抛 `AppRunnerException`，报错信息直接给出位置："Component 'X''s parameter in position K has not been connected!"（`tm_infra/tm_kit/infra/WithTimeData.hpp:2875`）。

**能不手写数字就不手写。** 两个替代方案：

- `GenericLift`（`tm_infra/tm_kit/infra/GenericLift.hpp:24`）能从函数签名自动推断该用哪种 lift。**但它对 `boost::hana::curry` 的产物不工作**，原因源码注释说了：curry 生成的 `operator()` 是重载的，推断不出唯一签名（`tm_examples/simple_demo/app_combination/MainLogicCombination.hpp:205`）。
- `DeclarativeGraph` 用位置索引代替函数名拼接，底层走的是上文的 `ActionAsSink<N,K>` / `Connect<N,K>` 类模板：

```cpp
// 来源：tm_examples/common_flow_util_tests/Tuple2VariantTest.cpp:26
infra::DeclarativeGraph<R>("", {
    {"importer", M::constFirstPushImporter<std::tuple<std::string, int>>({"abc", 10})}
    , {"t2v", M::dispatchTupleAction<std::string,int>()}
    /* ... printer1 / printer2 定义略 ... */
    , {"importer", "t2v"}
    , {"t2v", 0, "printer1"}
    , {"t2v", 1, "printer2"}
})(r);
```

`{"t2v", 0, "printer1"}` 里的 `0` 就是 K，但它是个普通的整数字面量，不是名字的一部分。这是可读性最好的写法。

## 实时 / 回测行为差异

**命名约定与元数上限在四种执行模式下完全一致**——这是故意的，也是业务代码能跨模式复用的前提。`liftPure2`、`actionAsSink_2_0`、`merge2` 在四个 app type 下都存在，签名相同。实测各模式的元数上限均为 20：`BasicWithTimeApp_Pure_Maybe_Kleisli_Piece.hpp` 与 `SinglePassIterationApp_Pure_Maybe_Kleisli_Piece.hpp` 的 `liftPure` 最大后缀都是 20，`ConnectN` 的 N 上限都是 20。

差异只在**哪些族存在**，这反映了各模式的执行机制不同：

| 族 | RealTimeApp | TopDown | SinglePass | BasicWithTime |
|---|---|---|---|---|
| ThreadedHandler | 有 | 无 | 无 | 无 |
| Provider_Adapter | 无 | 无 | 有 | 无 |
| TimeChecker | 有 | 有 | 无 | 无 |
| PureN / MaybeN / KleisliN 等分列 | 分成 7 个文件 | 分成 7 个文件 | 合并为 1 个 `Pure_Maybe_Kleisli` | 合并为 1 个 |
| Merge | 独立文件 | 独立文件 | 独立文件 | 并入 `VariantAndMerge` |

解读：

- `ThreadedHandler` 只有实时模式有，因为只有它可能多线程（`PossiblyMultiThreaded == true`，`RealTimeApp.hpp:679`）。
- `Provider_Adapter` 只有 `SinglePassIterationApp` 有，因为只有它是拉取式执行，需要把多路 provider 适配成单路（`ProviderAdapter_2_0`，`SinglePassIterationApp_Provider_Adapter_Piece.hpp:1`）。
- `BasicWithTimeApp` 的片段最少（5 个）且合并得最厉害，因为它不真正执行，生成的东西只要够过类型检查就行。相应地它的文件也最小（970 行 vs 实时模式 4005 行）。

另外单纯从体量看，`SinglePassIterationApp_ActionCore_Piece.hpp` 是全库最大的生成文件，**31615 行**，占生成代码总量的两成以上。

## 易错点

- **数字不一致**：`enhancedMaybe2` 配了 3 个显式模板参数，或者函数参数的 variant 有 3 路——编译失败，且报错极长。排查方法：看报错里的 `Action<std::variant<...>, ...>`，数一数 variant 里有几个类型，与你写的 N 对比。
- **K 从 0 还是 1 开始**：从 **0**。`actionAsSink_2_1` 是第二路，不是第二个 action。
- **以为 `_2_0` 的 `2` 是 K**：不是。第一个数字永远是总路数 N。`actionAsSink_20_19` 是"20 路输入里的最后一路"。
- **漏接某一路**：N 路 action 必须 N 路都接上，`finalize()` 会抛异常并指出是 position 几。
- **想用 `liftPure1`**：不存在，单输入就是 `liftPure`。
- **超过 20 路**：没有生成代码。把若干路先合成一个 struct 再传。
- **试图单独 include 一个 `*_Piece.hpp`**：必然失败，它们是类体内的片段，没有 include guard 也没有命名空间。
- **试图手工编辑生成文件**：别。它们成千上万行且高度重复，手改一处会与其余不一致，而且下次重新生成就丢了。要改行为，改生成器或改宿主头文件。
- **`GenericLift` 配 `boost::hana::curry` 不工作**：见上文，这时只能手写带数字的 lift。

## 第三方依赖

生成的片段**无第三方依赖**，与 tm_infra 整体一致，只用标准库（`std::variant`、`std::tuple`、`std::bitset`、`std::optional`、`std::shared_ptr`、实时模式下还有 `std::mutex`）。

示例代码里的 `boost::hana::curry` 来自 [Boost.Hana](https://www.boost.org/doc/libs/release/libs/hana/)，是 tm_examples 的依赖，不是 tm_infra 的。

## 存疑

- **生成器本身不在本仓库中**。`tm_infra/src/` 下只有四个 `.cpp`（`AppHeaders.cpp`、`ChronoUtils.cpp`、`GraphStructureBasedResourceHolderComponent.cpp`、`PidUtil.cpp`），没有脚本，`tm_infra/` 顶层也没有。所以"这些文件是机器生成的"这一判断依据是其形态——高度规整的重复、元数从 2 递增到 20、同一段逻辑在 50 个文件里逐字重复——而非找到了生成器。想新增元数或修改生成逻辑的人需要先找到或重写生成器。
- **`RequireMask` / `FanInParamMask` 在本仓库中无定义**。`tm_examples/transport_utils/historical_republisher.cpp:295` 用了它们，但对 `tm_infra`、`tm_basic`、`tm_transport` 全量 grep 都搜不到定义，而 `LiftParameters`（`WithTimeData.hpp:49`）只有 `SuggestThreaded` / `DelaySimulator` / `FireOnceOnly` 三个 setter。该示例文件应当编译不过，或对应了仓库之外的版本。照抄这一行会失败。`merge2` 的 `requireMask` 参数（`std::bitset<N>`）是真实存在的，概念相近，可作替代参考。

## 相关章节

- [00-overview.md](00-overview.md) —— 头文件地图与"多输入建模为 variant"的设计决策
- [01-app-types.md](01-app-types.md) —— 四种执行模式，解释了为何各模式的片段集合不同
- [03-nodes-and-lifting.md](03-nodes-and-lifting.md) —— pure / maybe / multi / kleisli / enhanced 的语义与 `GenericLift`
- [05-app-runner.md](05-app-runner.md) —— `actionAsSink` / `connect` / `execute` 与 finalize 时的连接校验
- [06-declarative-graph.md](06-declarative-graph.md) —— 用位置索引代替数字后缀
- [07-time-and-data.md](07-time-and-data.md) —— `LiftParameters`、`InnerData`、`TimeChecker` 的语义
- [../GLOSSARY.md](../GLOSSARY.md) —— 术语表
