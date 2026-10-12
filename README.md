---
title: TM Kit 开发参考
library: meta
headers: []
keywords: [TM Kit, 文档索引, README, tm_infra, tm_basic, tm_transport, tm_examples, 数据流框架, 量化交易, 实时, 回测]
---

# TM Kit 开发参考

TM Kit 是一个 C++17 数据流框架，让**同一份业务逻辑**既能在实时（多线程、事件驱动）下运行，也能在回测（单线程、数据驱动）下运行。本套文档面向两类读者：需要快速定位"我要做 X，该用哪个类"的人类开发者，以及需要检索 API 细节的大模型。

仓库原有的三份 README 只讲了设计理念与安装，没有 API 级参考。本目录补齐这一层。

> **构建与安装**不在本套文档范围内，见 [BUILD.md](BUILD.md)。

## 从哪开始

| 你的情况 | 读什么 |
|---|---|
| 第一次接触 TM Kit | [QUICK_START](QUICK_START.md) —— 从零写第一个程序 |
| 已经会写，想知道坑在哪 | [PATTERNS](PATTERNS.md) —— 跨库模式与易错点 |
| 找一个功能在哪个头文件 | 下面的[全文章节索引](#全文章节索引)，或各章的 front-matter `headers` 字段 |
| 想学某个示例 | [EXAMPLES_MAP](EXAMPLES_MAP.md) —— 19 个示例目录逐一归类 |
| 依赖出问题 | [THIRD_PARTY](THIRD_PARTY.md) —— 库索引 + `.pc` 修补总表 |
| 术语看不懂 | [GLOSSARY](GLOSSARY.md) —— 中英对照 |

## 三个库的分工

```
tm_infra  ──►  tm_basic  ──►  tm_transport  ──►  tm_examples
```

| 库 | 是什么 | 依赖 |
|---|---|---|
| **tm_infra** | 数据流图的核心：节点类型、提升操作、Environment 模型、AppRunner、执行模式 | **无第三方依赖** |
| **tm_basic** | 基础工具：四套时钟、结构体反射与序列化、日志、通用流工具、量化值类型、事务与共享链 | tm_infra |
| **tm_transport** | 进程间通信：多传输抽象的广播与远程设施、共享链后端、心跳服务发现、安全 | tm_infra + tm_basic + 各传输的第三方库 |

**核心概念**（详见 [GLOSSARY](GLOSSARY.md)）：

- **节点** —— importer（数据入图）/ action（变换）/ exporter（数据出图）/ facility（请求-响应）
- **Environment** —— 若干 component 的虚继承混合体，承载时钟、日志、传输等能力
- **App 类型 `M`** —— `RealTimeApp` / `SinglePassIterationApp` / `TopDownSinglePassIterationApp` / `BasicWithTimeApp`，决定图的执行语义
- **AppRunner** —— 注册节点、连接、校验、驱动图的对象

**一句话理解框架**：业务代码对 `M` 模板化，换 `M` 就换了执行模式。

## 全文章节索引

### tm_infra —— 数据流核心

| # | 章节 | 关键词 | 覆盖头文件 |
|---|---|---|---|
| 00 | [概览](tm_infra/00-overview.md) | 图模型、三类节点、多输入 variant、多输出 tuple | —— |
| 01 | [App 类型](tm_infra/01-app-types.md) | RealTimeApp / SinglePassIterationApp / TopDown / BasicWithTime | `RealTimeApp.hpp`, `SinglePassIterationApp.hpp`, `TopDownSinglePassIterationApp.hpp` |
| 02 | [Environments](tm_infra/02-environments.md) | 组件组合模型、虚继承混合 | `Environments.hpp` |
| 03 | [节点提升](tm_infra/03-nodes-and-lifting.md) | liftPure / liftMaybe / liftMulti / kleisli / enhanced / LiftParameters | `GenericLift.hpp`, `KleisliUtils.hpp` |
| 04 | [Facilities](tm_infra/04-facilities.md) | on-order facility 四种变体、图中成环 | `WithTimeData.hpp` |
| 05 | [AppRunner](tm_infra/05-app-runner.md) | 连接、命名、Graphviz、controlAll、GraphCheck | `WithTimeData.hpp` |
| 06 | [DeclarativeGraph](tm_infra/06-declarative-graph.md) | 声明式建图 | `DeclarativeGraph.hpp` |
| 07 | [时间与数据](tm_infra/07-time-and-data.md) | WithTime、VersionedData、ChronoUtils | `WithTimeData.hpp`, `VersionedData.hpp` |
| 08 | [Runner 与控制](tm_infra/08-runners-and-control.md) | SynchronousRunner、TerminationController、ControllableNode、Trace | `TerminationController.hpp` |
| 09 | [生成的元数文件](tm_infra/09-generated-pieces.md) | `*_Piece.hpp` 的生成规律与元数上限（**不逐个展开**） | `*_Piece.hpp` |

### tm_basic —— 基础工具

| # | 章节 | 关键词 | 覆盖头文件 |
|---|---|---|---|
| 00 | [概览](tm_basic/00-overview.md) | —— | —— |
| 01 | [时钟](tm_basic/01-clocks.md) | real_time / single_pass_iteration / top_down / empty 四套时钟 | `*/ClockComponent.hpp` |
| 02 | [结构反射](tm_basic/02-struct-field-info.md) | `TM_BASIC_CBOR_CAPABLE_STRUCT*` 宏族、StructFieldInfo | `SerializationHelperMacros.hpp`, `StructFieldInfo*.hpp` |
| 03 | [序列化](tm_basic/03-serialization.md) | ByteData、CBOR、Proto、JSON、simdjson | `ByteData.hpp`, `ProtoInterop.hpp`, `NlohmannJsonInterop.hpp` |
| 04 | [日志](tm_basic/04-logging.md) | SpdLoggingComponent、TrivialBoostLoggingComponent | `SpdLoggingComponent.hpp` |
| 05 | [CommonFlowUtils](tm_basic/05-common-flow-util.md) | 批处理、时间窗口、同步合并、时间移位 | `CommonFlowUtils.hpp` |
| 06 | [量化值类型](tm_basic/06-value-types.md) | FixedPrecisionShortDecimal、DateHolder、ConstType、SingleLayerWrapper | `FixedPrecisionShortDecimal.hpp`, `DateHolder.hpp` |
| 07 | [CSV/HDF5/FlatPack](tm_basic/07-csv-hdf5-flatpack.md) | 批量 I/O 与 DynamicView | `StructFieldInfoBased*Utils.hpp` |
| 08 | [共享链](tm_basic/08-shared-chain.md) | simple_shared_chain：Reader/Writer/Folder | `simple_shared_chain/*.hpp` |
| 09 | [事务 v2](tm_basic/09-transaction.md) | DataStream、TransactionFacility、GeneralSubscriber | `transaction/v2/*.hpp` |
| 10 | [AppRunnerUtils](tm_basic/10-app-runner-utils.md) | 类型适配、退出计时器、多图交错、图控制 | `AppRunnerUtils.hpp`, `MultiAppRunnerUtils.hpp` |

### tm_transport —— 进程间通信

| # | 章节 | 关键词 | 覆盖头文件 |
|---|---|---|---|
| 00 | [概览](tm_transport/00-overview.md) | ConnectionLocator、信道字符串、能力矩阵 | `ConnectionLocator.hpp` |
| 01 | [广播](tm_transport/01-broadcast.md) | listener / publisher / 心跳服务发现 | `MultiTransportBroadcast*Utils.hpp` |
| 02 | [远程设施](tm_transport/02-facilities.md) | 请求-响应、服务端包装、合成设施 | `MultiTransportRemoteFacility*.hpp` |
| 03 | [各传输详解](tm_transport/03-transports/) | 12 个传输的 locator 语法与能力（见下表） | 各传输子目录 |
| 04 | [共享链后端](tm_transport/04-shared-chains.md) | Etcd / Redis / 共享内存链 | `SharedChainCreator.hpp` |
| 05 | [心跳与告警](tm_transport/05-heartbeat-and-alert.md) | HeartbeatMessage、服务发现前提 | `HeartbeatAndAlertComponent.hpp` |
| 06 | [安全与身份校验](tm_transport/06-security.md) | Hook、identity checker、签名、TLS | `ByteDataHook.hpp`, `TLSConfigurationComponent.hpp` |
| 07 | [键值存储组件](tm_transport/07-kv-store-components.md) | 只读查询、DB 表事务、DB 导入导出 | `complex_key_value_store_components/*`, `db_table_importer_exporter/*` |

#### 03-transports 的 12 个传输

| 传输 | 广播 | facility | 章节 |
|---|---|---|---|
| RabbitMQ | ✓ | ✓ | [rabbitmq.md](tm_transport/03-transports/rabbitmq.md) |
| ZeroMQ | ✓ | ✗ | [zeromq.md](tm_transport/03-transports/zeromq.md) |
| Multicast（UDP 组播） | ✓ | ✗ | [multicast.md](tm_transport/03-transports/multicast.md) |
| Singlecast（UDP 单播） | ✓ | ✗ | [singlecast.md](tm_transport/03-transports/singlecast.md) |
| Redis | ✓ | ✓ | [redis.md](tm_transport/03-transports/redis.md) |
| NATS | ✓ | ✓ | [nats.md](tm_transport/03-transports/nats.md) |
| NNG | ✓ | ✗ | [nng.md](tm_transport/03-transports/nng.md) |
| SharedMemoryBroadcast | ✓ | ✗ | [shared_memory_broadcast.md](tm_transport/03-transports/shared_memory_broadcast.md) |
| SocketRPC | ✗ | ✓ | [socket_rpc.md](tm_transport/03-transports/socket_rpc.md) |
| WebSocket | ✓ | ✓ | [websocket.md](tm_transport/03-transports/websocket.md) |
| JsonREST | ✗ | ✓ | [json_rest.md](tm_transport/03-transports/json_rest.md) |
| GrpcInterop | ✗ | ✓ | [grpc_interop.md](tm_transport/03-transports/grpc_interop.md) |

### 跨库文档

| 文档 | 内容 |
|---|---|
| [AGENT_INDEX](AGENT_INDEX.md) | **给 agent 的入口**：铁律 12 条 + 任务路由表 + 章节清单（≈5k token，可常驻） |
| [QUICK_START](QUICK_START.md) | 从零搭第一个程序、Environment 清单、建图三种写法、项目 meson 配置 |
| [PATTERNS](PATTERNS.md) | 跨模块模式与易错点、排错清单 |
| [EXAMPLES_MAP](EXAMPLES_MAP.md) | 19 个示例目录逐一归类 + 推荐阅读顺序 |
| [THIRD_PARTY](THIRD_PARTY.md) | 第三方库索引、8 处 `.pc` 修补、链接错误排查流程 |
| [GLOSSARY](GLOSSARY.md) | 术语中英对照（各章不得自创译名） |
| [DOWNSTREAM](DOWNSTREAM.md) | 上层项目如何接入：submodule、CLAUDE.md 片段、版本对齐、CI |
| [CONTRIBUTING-DOCS](CONTRIBUTING-DOCS.md) | 本套文档的写作规范 |

**用 agent 开发上层项目**：先读 [DOWNSTREAM](DOWNSTREAM.md) 接入，日常检索用 `tools/tm_docs`：

```bash
./tools/tm_docs find "事务 订阅"                       # 按关键词找章节
./tools/tm_docs find --task "跨进程发请求收响应"
./tools/tm_docs headers CommonFlowUtils.hpp            # 头文件反查
./tools/tm_docs show tm_basic/09-transaction --section 易错点
```

## 按任务查

| 我要…… | 看 |
|---|---|
| 写一个能在实时和回测下都跑的程序 | [QUICK_START](QUICK_START.md) §6、[tm_infra/01](tm_infra/01-app-types.md) |
| 定义一个有字段名反射的结构体 | [tm_basic/02](tm_basic/02-struct-field-info.md) |
| 选序列化格式（CBOR / Proto / JSON） | [tm_basic/03](tm_basic/03-serialization.md) |
| 表示价格、日期、编译期常量 | [tm_basic/06](tm_basic/06-value-types.md) |
| 做 5 分钟滑动窗口 / 批量聚合 | [tm_basic/05](tm_basic/05-common-flow-util.md) |
| 发一组成交单并收响应 | [tm_infra/04](tm_infra/04-facilities.md) |
| 跨进程分发行情 | [tm_transport/01](tm_transport/01-broadcast.md)、[03-transports](tm_transport/03-transports/) |
| 让服务自动发现彼此 | [tm_transport/05](tm_transport/05-heartbeat-and-alert.md) |
| 做事务型状态服务（带订阅） | [tm_basic/09](tm_basic/09-transaction.md) |
| 做事件溯源 / 可重放的状态机 | [tm_basic/08](tm_basic/08-shared-chain.md) + [tm_transport/04](tm_transport/04-shared-chains.md) |
| 把数据库表当作数据源 | [tm_transport/07](tm_transport/07-kv-store-components.md) |
| 加签名 / 身份校验 / TLS | [tm_transport/06](tm_transport/06-security.md) |
| 把 facility 暴露给 C#/Python/前端 | [03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md)、[websocket](tm_transport/03-transports/websocket.md)、[json_rest](tm_transport/03-transports/json_rest.md) |
| 让两个 runner 交错回测 | [tm_basic/10](tm_basic/10-app-runner-utils.md) |
| 输出 Graphviz 图 | [tm_infra/05](tm_infra/05-app-runner.md) |

## 按头文件查

每篇文档的 front-matter 有 `headers` 字段，列出该章覆盖的头文件。快速反查：

```bash
# 找某个头文件在文档中的记载
grep -rl "CommonFlowUtils.hpp" tm_kit_reference/

# 按关键词找章节
grep -rl "FixedPrecisionShortDecimal" tm_kit_reference/
```

## 阅读约定

- 正文中文，API 名、类型名、宏名保持英文原样
- 源码引用写成 `path/to/file.hpp:123`（相对仓库根），终端可点击
- 示例代码均出自或改写自 `tm_examples/`，并注明来源；简化过的标注"（已简化）"
- 标"示例代码库中暂无用例"的表示该特性在 `tm_examples/` 中找不到用例，只给出头文件中的真实签名
- 每章统一节序：用途 → 头文件/命名空间 → 核心类型与签名 → 最小可用示例 → 实时/回测行为差异 → 易错点 → 第三方依赖 → 相关章节
- 各章末尾的"相关章节"提供双向链接

**不在本套文档范围内**：TypeScript（`TMTransportDotNet` / `node_lib`）与 C#/Python 语言绑定的完整参考——它们在各概览与 [03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md) 中有定位说明，但不展开。

## 本套文档的边界

- `tm_infra/tm_kit/infra/*_Piece.hpp` 是机器生成的元数展开（单文件可达 3 万行）。本套文档**只归纳其签名族与元数上限**，不逐个展开，见 [tm_infra/09](tm_infra/09-generated-pieces.md)。
- 文档中的示例是**节选**，为可读性做了简化，不作为可编译单元。可直接编译的完整示例见 [EXAMPLES_MAP](EXAMPLES_MAP.md) 指向的 `tm_examples/` 源文件。
- 行号引用基于当前仓库状态。源码变动后行号可能漂移——文件路径始终有效。
