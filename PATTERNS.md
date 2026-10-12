---
title: 跨库模式与易错点
library: meta
headers: []
keywords: [patterns, 模式, 易错点, pitfalls, 实时回测双模, 时钟, 生命周期, 线程安全, 类型推导, 序列化兼容, 服务发现, 编译时期, 排错]
---

# 跨库模式与易错点

各章节的"易错点"聚焦于单模块内部。本文汇总**跨模块**的模式与陷阱——那些只有把 `tm_infra` + `tm_basic` + `tm_transport` 放在一起看才会暴露的问题。

## 1. 实时 / 回测双模：四条铁律

这是 TM Kit 的立身之本，也是最容易出 BUG 的地方。

### 1.1 业务逻辑必须对 App 类型模板化

**错误**：在业务函数里写死 `using M = infra::RealTimeApp<Env>;`。

**正确**：把 `M` 作为模板参数传进来。

```cpp
// 来源：tm_examples/simple_demo/app_combination/MainLogicCombination.hpp 的组织方式
template <class R, class ...Deps>
auto MainLogicCombination(R &r, typename R::EnvironmentType *env
    , MainLogicInput<R> &&input, int logicChoice, std::string const &alertTopic);
```

这样实时可执行文件传 `AppRunner<RealTimeApp<Env>>`，回测传 `AppRunner<SinglePassIterationApp<Env>>`，**组合代码一字不改**。

### 1.2 实时与回测的驱动语义完全不同

| | `RealTimeApp` | `SinglePassIterationApp` |
|---|---|---|
| App 层 `finalize()` 语义 | 启动各节点后台线程后**立即返回** | **内部执行完整单遍迭代循环**，直到 `finalFlag` 或环境退出 |
| 程序如何结束 | 靠 `terminationController(...)` 维持主线程 | `finalize()` 返回即结束 |
| 有没有 `r.run()` | 没有 | **也没有**——迭代在 finalize 里 |

注意这里说的是 **App 层** 的 `finalize()`（`RealTimeApp::finalize()` / `SinglePassIterationApp::finalize()`，返回 `std::function<void(StateT*)>`）。业务代码调的是 **`AppRunner::finalize()`**，它只做两件事：先 `finalizeBegin()` 校验图，再 `m_.finalize()(env_)` 调用 App 层。所以"回测会跑完整遍"发生在 App 层那一句里。

`WithTimeData.hpp:2980` 是唯一的真相：

```cpp
void finalize() {
    finalizeBegin();
    m_.finalize()(env_);     // ← 单遍迭代 App 的 finalize() 返回的正是 while(env->running()) 循环
}
```

多图交错跑才需要额外调用：`MultiAppRunnerUtilComponents::run(r1, r2)`（见 [tm_basic/10](tm_basic/10-app-runner-utils.md)）。

### 1.3 传输层只在实时模式可用

`MultiTransportBroadcastListener`、`MultiTransportRemoteFacility`、`SyntheticMultiTransportFacility` 都把 `M` 硬编码为 `infra::RealTimeApp<Env>`：

- `tm_kit/transport/MultiTransportBroadcastListener.hpp:339`
- `tm_kit/transport/MultiTransportRemoteFacility.hpp:123`
- `tm_kit/transport/SyntheticMultiTransportFacility.hpp:22`（`static_assert`）

放进回测 App 会得到一大片模板实例化错误。回测的替代方案：

| 实时用的 | 回测替换为 |
|---|---|
| `oneBroadcastListener<T>` | 文件 importer（CSV / HDF5 / `ByteDataWithTopicRecordFile`） |
| `setupOneNonDistinguishedRemoteFacility` | 本地 mock facility（直接赋给同一个 `FacilitioidConnector` 变量） |
| 心跳服务发现 | 配置里写死的信道地址 |
| 共享链 | 仍可用——链本来就是跨模式设计（见 1.4） |

### 1.4 时间戳来源决定可重放性

链（chain）之所以能忠实重放，是因为它带 `infra::HiddenTimeDependencyComponent`，时间戳来自**数据本身**而非环境时钟。任何依赖 `env->now()` 的逻辑在回测中都会读到"回测当前时刻"而非"数据时刻"。

写回测友好的代码：**优先用数据自带的时间字段**，少用 `env->now()`。

## 2. 类型系统：编译期决定的事

### 2.1 多输入 = `variant`，多输出 = `tuple`

框架不支持"节点有两个独立输入"。多个输入必须先用 `std::variant<A,B>` 合并（`merge` 族），多个输出用 `std::tuple<X,Y>`。

**症状**：`r.connect(src, sink)` 报类型不匹配，而你以为"两个输入应该能一起接"。

### 2.2 identity checker 会改变 facility 的请求类型

环境里有 `ClientSideAbstractIdentityAttacherComponent<Identity, Request>` 时，facility 的请求类型变成 `std::tuple<Identity, Request>`：

```cpp
// tm_kit/transport/AbstractIdentityCheckerComponent.hpp:52
using FullRequestType = std::tuple<IdentityType, Request>;
```

这是**编译期**的。加/删 identity 组件会让整条链上的类型全部改变——包括 `FacilitioidConnector<A,B>` 的 `A`。所以"运行时开关身份校验"是不可能的。

### 2.3 `CheckTimeComponent<true>` 与 `<false>` 是不同类型

`Environments.hpp:42` 的 `template <bool DoCheck> struct CheckTimeComponent`。`Environment<CheckTimeComponent<true>, ...>` 与 `Environment<CheckTimeComponent<false>, ...>` 是两个完全不同的类型，不能互相赋值，也不能共用同一个 `AppRunner` 实例化。

### 2.4 `transaction::current` 就是 `v2`

`tm_basic/tm_kit/basic/transaction/TransactionClient.hpp:14`：`namespace current = v2;`

看到 `transaction::current::` 不要以为存在另一套 API。

### 2.5 `TriggerT` 决定返回 Importer 还是 Action

`SharedChainCreator` 的 `reader<ChainData, ChainItemFolder, TriggerT, ...>`：

- `TriggerT = void`（默认）→ 返回 `Importer<ResultType>`
- 给了 `TriggerT` → 返回 `Action<TriggerT, ResultType>`

差别是**编译期**的，写错导致下游类型不匹配。回测中由时钟驱动读取时通常需要非 `void` 的 `TriggerT`。

### 2.6 宏生成的结构体才有反射

以下功能**全部**要求 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE` 之类的宏：

| 功能 | 要求 |
|---|---|
| CSV / HDF5 / FlatPack 读写 | `StructFieldInfo<T>::HasGeneratedStructFieldInfo` |
| `DBTableImporterFactory` / `DBTableExporterFactory` | 同上（`DBTableImporterFactory.hpp:59`） |
| HDF5 | 还要 `StructFieldOffsetInfo<T>::HasGeneratedStructFieldOffsetInfo` |
| `StructFieldInfoBasedHash`（map key） | `StructFieldInfo<T>` |
| gRPC interop | `ProtobufStyleSerializableChecker<T>::IsProtobufStyleSerializable()` |

只写了 `struct Foo { ... };` 而没有宏，会在某处 `enable_if` 失败——报错信息通常不直观。

## 3. 序列化兼容性

### 3.1 跨进程/跨时间的数据必须字段名兼容

链上的历史数据、wire 上的消息，都要考虑"对端是旧版本"的情况。**改结构体字段名等于让历史数据读不出来**。

安全的变化：新增字段（旧数据缺该字段 → 默认值）。
危险的变化：改字段名、改字段类型、改字段顺序（对无字段名的 CBOR 编码尤其致命）。

### 3.2 三种编码的互操作边界

| 包装 | 格式 | 能与其他语言互通 | 备注 |
|---|---|---|---|
| `basic::CBOR<T>` | CBOR（带字段名映射） | 是（需 CBOR 库） | 默认选择 |
| `basic::proto_interop::Proto<T>` | protobuf | 是（需 .proto） | gRPC 必须用 |
| `basic::nlohmann_json_interop::Json<T>` | JSON | 是（人类可读） | 前端场景 |
| `basic::FlatPack<T*>` | FlatPack | 是 | **不注册到 `RunSerializer` 体系**，需手动调用 |
| `std::void_t` | 不包装 | —— | 直接用内层类型的 CBOR |

`FixedPrecisionShortDecimal` 是特例：CBOR 编成 `tuple<precision, underlying>`（无损），JSON 编成字符串，**Proto 编成 `double`（有精度损失）**。跨语言用 Proto 传价格时要注意这一点。

### 3.3 `WireToUserHook` 失败是静默的

`tm_kit/transport/ByteDataHook.hpp:13`：`WireToUserHook` 返回 `std::optional<ByteData>`。验签失败 → `nullopt` → **消息被丢弃，无日志无异常**。

"心跳/数据莫名收不到"时，先查 hook 配置（密钥、name tag）是否匹配。

## 4. 线程与生命周期

### 4.1 实时模式下节点各跑各的线程

`RealTimeApp` 的每个 importer/exporter/标记了 `SuggestThreaded(true)` 的 action 都有自己的线程。后果：

- 共享可变状态必须加锁（除非该 App 的 `PossiblyMultiThreaded` 为 false）
- `CommonFlowUtils` 的很多工具有 `useMutex` / `suggestThreaded` 参数，**默认值与 `M::PossiblyMultiThreaded` 一致**——回测下默认不加锁，实时下默认加锁
- `rightShift` 用了 `static std::deque` 缓冲（`CommonFlowUtils.hpp:1667`），**同一进程内多处调用会共享缓冲区**。每次需要新的右移节点时要重新调用 `rightShift`，不要复用返回值

### 4.2 `env` 与外部资源的生命周期必须覆盖图

用 `std::make_shared<soci::session>` 之类的共享指针，或在 `main` 作用域持有。图析构时节点会访问这些资源——`session` 先于 `AppRunner` 析构就是悬空引用。

`r.preservePointer(ptr)` 可以让 runner 帮忙持有指针（见 `WithTimeData.hpp:2993`）。

### 4.3 传输节点会在 `finalize()` 时启动线程

`MultiTransportBroadcastListener` 等是 `IExternalComponent`，`finalize()` 里 `c->start(env)` 启动它们。因此：

- 在 `finalize()` 之后注册节点是无效的（不参与校验也不启动）
- 需要延迟补边用 `r.registerTouchUp(...)`

### 4.4 `SharedChainCreator` 每进程一个实例

它内部用 `unordered_map` 缓存链对象（`SharedChainCreator.hpp:257` 的 `getChain`），保证同名链只建一次。每次调用都 new 一个 creator 会对同一后端建多条独立连接。

## 5. 传输与服务发现

### 5.1 心跳是服务发现的前提

`setupBroadcastListenerThroughHeartbeat` 与 `setupOneNonDistinguishedRemoteFacility` 都依赖一个已经建立的 `heartbeatSource`。忘记：

1. 服务端 `initializeHeartbeatAndAlertComponent` + `attachHeartbeatAndAlertComponent`
2. 客户端先建心跳订阅

→ 表现为"订阅建立了但收不到数据"或"请求发出无响应"，**不报错**。

### 5.2 心跳周期必须小于客户端 `ttl`

`attachHeartbeatAndAlertComponent(period)` 的服务端周期，与客户端 `ttl`（默认 3 秒）、`checkPeriod`（默认 5 秒）共同决定失效判定。**`period > ttl` 会让服务被误判为下线**。

合理关系：`period < ttl`，并留网络抖动余量。

### 5.3 `furthestPoint` 默认 24 小时

`attachHeartbeatAndAlertComponent` 的 `furthestPoint` 默认 `std::chrono::hours(24)`（`HeartbeatAndAlertComponent.hpp:358`）。**连续运行超过 24 小时后心跳静默停止**，客户端开始报告服务下线。长跑程序必须显式放大。

### 5.4 信道的"名字"与"地址"是两回事

`addBroadcastChannel(name, channel)`：`name` 是**发现键**（客户端按它查找），`channel` 才是**地址**。客户端 `setupBroadcastListenerThroughHeartbeat(..., broadcastSourceLookupName, ...)` 传的字符串必须与服务端的 `name` 完全一致。

同理，facility 的 `facilityRegistrationName` 必须两端一致。

### 5.5 服务名的正则匹配

`initializeHeartbeatAndAlertComponent` 的 `identity` 写入 `senderDescription`，客户端用 `std::regex` 匹配。**服务端改名，所有客户端正则都要改**。名字里含 `.` 等正则元字符时要转义。

### 5.6 topic 通配符语义因传输而异

框架把 `#` 统一转成 `*` 给 Redis/NATS，但语义并不等价：

| 传输 | 多级通配 | 单级通配 | 分词符 |
|---|---|---|---|
| RabbitMQ | `#` | `*` | `.` |
| Redis | `*`（任意长度） | `?` | 无（glob） |
| NATS | `>`（仅末尾） | `*` | `.` |
| ZeroMQ / NNG | 无（`std::string` 是**精确**匹配，要模糊用 `std::regex`） | —— | —— |

写跨传输的 topic 时只依赖 `#` 作为多级通配。

### 5.7 无 broker 的传输不保留消息

ZeroMQ / multicast / singlecast / NNG / Redis pub-sub / NATS（非 JetStream）都是 fire-and-forget。**订阅者启动前的消息永久丢失**。

需要"新订阅者拿到当前状态"的模式：订阅后用一次 facility 请求拉快照，再靠广播接收增量。

### 5.8 回测需要把实时数据落盘

由于 5.7，用无 broker 传输录制的实时数据必须**在实时阶段**写入文件（如 `ByteDataWithTopicRecordFileImporterExporter`）或链，回测才有数据可读。

## 6. 事务与状态

### 6.1 `TI` 与 `DI` 必须共享 GV/Key/Version/Data 类型

`TransactionProcessor` 的特化约束（`tm_kit/basic/transaction/v2/TransactionFacility.hpp:70-75` 的 `enable_if`）：`TransactionInterface` 与 `DataStreamInterface` 的 `GlobalVersionType`/`Key`/`Version`/`Data` 必须逐一相同。类型不一致直接编译失败。

### 6.2 `DataStreamEnvComponent::initialize` 必须发出全量快照

服务端启动时 `initialize` 要把当前全量数据作为 `DI::FullUpdate` 推出去，否则新订阅者拿不到初始状态（只有后续的增量）。

### 6.3 `TransactionEnvComponent` 的 `dataDelta` 可以是 `nullptr`

`tm_kit/basic/transaction/v2/TransactionEnvComponent.hpp:13` 的注释说明：`acquireLock`/`releaseLock` 的 `dataDelta` 参数在纯锁操作场景下可能为空。

### 6.4 `TriviallyMerge` 的语义是 `d = delta`

`DefaultUtilities` 里的 `TriviallyMerge` 直接赋值而非合并。对于"每个字段都随每次更新完整给出"的数据模型是对的；对"只给出变化字段"的模型会丢数据。

## 7. 构建与依赖

### 7.1 `.pc` 改完必须完整重配置

Meson 在 **configure 阶段**缓存依赖信息。编辑 `.pc` 后仅跑 ninja 无效：

```bash
source ./build-env-setting-rocky.sh
ASSUME_YES=1 ./build.sh <project>     # ASSUME_YES 隐含 clean rebuild
```

### 7.2 传递依赖放 `Requires:`，不要放 `Libs:`

pkg-config 只有读到 `Requires: B` 才会展开 B 自身的依赖链。把 `-lB` 直接写进 `Libs:` 会丢掉 B 的 Cflags 和它自己的依赖。

这条规则修好了 `soci → odbc → libltdl.a` 与 `soci → mysqlclient`（`mysql.h` 的 include 路径）两个问题。

### 7.3 `--as-needed` 丢弃 `-l` 形式的库时改用绝对路径

写 `${libdir}/libfoo.a`。同时**先核对库名与磁盘文件名**——`libnats` vs `libnats_static` 就是这么踩的。

详见 [THIRD_PARTY](THIRD_PARTY.md) 的 `.pc` 修补总表。

### 7.4 不要为了省事用 `AllNetworkTransportComponents`

它把所有传输的第三方库都链接进二进制（含 gRPC + Abseil + protobuf）。按需列出用到的组件。同理 `AllChainComponents` 会连带引入 Etcd → gRPC。

### 7.5 `ninja -j4` 是硬约束

系统资源限制，不是性能建议。

### 7.6 构建日志可达 GB 级，用定向 grep

```bash
grep -n '^FAILED:' build_debug.log                       # 失败的构建目标
grep -n 'error:' build_debug.log | grep -v 'warning:'    # 真正的错误
```

## 8. 排错清单

遇到问题时按这个顺序排查：

| 症状 | 先查 |
|---|---|
| 链接时 "undefined reference" | 对应 `.pc` 的 `Libs`/`Requires`（[THIRD_PARTY](THIRD_PARTY.md) 2.3 的流程） |
| 一大堆模板实例化错误 | App 类型不匹配（传输节点用在回测 App？）；`enable_if` 失败（缺 `StructFieldInfo` 宏？） |
| 订阅了但收不到数据 | 心跳是否建立；服务名/信道名是否一致；hook 配置是否匹配；exchange/队列名拼写 |
| facility 请求无响应 | 服务端是否在线；`facilityRegistrationName` 是否一致；`ttl`/`period` 关系 |
| 回测结果与实时不一致 | 是否用了 `env->now()`；数据库查询是否读了"现在"而非"当时"；`whereClause` 是否加 |
| 程序跑一段时间后心跳停了 | `furthestPoint` 默认 24 小时（见 5.3） |
| 图不再推进（卡死） | facility 的 1:1 约束（`setupVIEFacilitySelfLoopAndWait`）；`synchronizer2` 等不到配对 |
| 时间戳倒退 | `CheckTimeComponent<true>` 会报错；检查上游是否用了多个时钟源 |

## 9. 相关章节

- [QUICK_START](QUICK_START.md) — 从零搭第一个程序
- [THIRD_PARTY](THIRD_PARTY.md) — 依赖与 `.pc` 修补
- [EXAMPLES_MAP](EXAMPLES_MAP.md) — 每个模式在哪个示例里
- [GLOSSARY](GLOSSARY.md) — 术语中英对照
- [tm_infra/00-overview](tm_infra/00-overview.md) — 数据流图模型
- [tm_infra/01-app-types](tm_infra/01-app-types.md) — App 类型对照
- [tm_basic/10-app-runner-utils](tm_basic/10-app-runner-utils.md) — 退出计时器与多图交错
- [tm_transport/05-heartbeat-and-alert](tm_transport/05-heartbeat-and-alert.md) — 服务发现
