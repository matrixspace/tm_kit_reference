---
title: tm_examples 索引
library: meta
headers: []
keywords: [tm_examples, 示例索引, examples map, simple_demo, db_subscription, db_one_list_subscription, transaction_redundancy_test, simple_demo_chain_version, common_flow_util_tests, serialization_test, clock_logic_test, transport_utils, websocket_test, json_rest_test, rpc_examples, shared_chain_test, csv_test, hdf5_test, bcl_compat_test, synthetic_facility_test]
---

# tm_examples 索引

`tm_examples/` 下 19 个示例目录（不含 `external/` 与 `prebuild/`），每个都演示了一组特定能力。本表回答"想学 X，去看哪个示例"。

所有示例**无 install 目标**，可执行文件留在 `tm_examples/builddir_<type>/` 下。

## 1. 按主题索引

| 想了解 | 去看 | 对应文档 |
|---|---|---|
| 同一份业务逻辑跑实时 + 回测 | `simple_demo/` | [PATTERNS](PATTERNS.md)、[tm_infra/01](tm_infra/01-app-types.md) |
| 事件溯源 / 链式持久化 | `simple_demo_chain_version/`、`shared_chain_test/` | [tm_basic/08](tm_basic/08-shared-chain.md)、[tm_transport/04](tm_transport/04-shared-chains.md) |
| 事务型键值存储（服务端 + 客户端） | `db_subscription/`、`db_one_list_subscription/` | [tm_basic/09](tm_basic/09-transaction.md) |
| 事务的冗余与反向广播 | `transaction_redundancy_test/` | [tm_basic/09](tm_basic/09-transaction.md) |
| 通用流处理工具 | `common_flow_util_tests/` | [tm_basic/05](tm_basic/05-common-flow-util.md)、[tm_basic/10](tm_basic/10-app-runner-utils.md) |
| 序列化格式与互操作 | `serialization_test/` | [tm_basic/03](tm_basic/03-serialization.md) |
| 时钟、定时器、超时 | `clock_logic_test/` | [tm_basic/01](tm_basic/01-clocks.md) |
| 传输层的各种用法 | `transport_utils/` | [tm_transport/00](tm_transport/00-overview.md) |
| WebSocket（含前端） | `websocket_test/`、`simple_demo/qt_client/` | [03-transports/websocket](tm_transport/03-transports/websocket.md) |
| JSON REST | `json_rest_test/` | [03-transports/json_rest](tm_transport/03-transports/json_rest.md) |
| gRPC 互操作 | `grpc_interop_test/`、`db_*/` | [03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md) |
| 远程设施与合成设施 | `rpc_examples/`、`synthetic_facility_test/` | [tm_transport/02](tm_transport/02-facilities.md) |
| CSV / HDF5 批量 I/O | `csv_test/`、`hdf5_test/` | [tm_basic/07](tm_basic/07-csv-hdf5-flatpack.md) |
| C# / .NET 兼容类型 | `bcl_compat_test/` | [tm_transport/03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md) |

## 2. 逐个说明

### `simple_demo/` — 框架的范本

最完整、最值得先读的示例。演示"同一份业务组合跑实时与回测"。

```
simple_demo/
├── plain_executables/     # 明文版：DataSource（发布）+ MainLogic（消费）+ Calculator
├── secure_executables/    # 加密版：加了 Diffie-Hellman 密钥交换与签名 hook
├── qt_client/chart/       # Qt 前端，心跳发现 + 信道解析 + 动态订阅
├── client/data_display/   # 客户端数据展示流程
├── app_combination/       # MainLogicCombination.hpp：实时/回测共用的业务组合
├── program_logic/         # MainLogic.hpp：业务逻辑本体
├── external_logic/        # 外部逻辑（如 mock calculator）
├── security_logic/        # 密钥交换与签名
└── data_structures/       # 共享数据结构定义
```

**关键看点**：
- `plain_executables/MainLogic.cpp:101–116` —— `if (isReal) { 网络设施 } else { 本地 mock }`，这是全框架最重要的模式
- `plain_executables/DataSource.cpp:61` —— `setDocRoot` 同时托管前端页面与 REST 端点
- `plain_executables/DataSource.cpp:72–83` —— 同一份数据发往 ZeroMQ 和 WebSocket 两个信道
- `qt_client/chart/tmPart.cpp:198–204` —— 从心跳里取出发布者声明的信道再订阅（"换传输不改代码"）

对应文档：[tm_infra/01](tm_infra/01-app-types.md)、[tm_basic/10](tm_basic/10-app-runner-utils.md)、[tm_transport/01](tm_transport/01-broadcast.md)、[02](tm_transport/02-facilities.md)、[05](tm_transport/05-heartbeat-and-alert.md)、[06](tm_transport/06-security.md)

### `simple_demo_chain_version/` — 事件溯源

把链（chain）引入 `simple_demo` 的架构：每个业务事件 append 到共享链，状态由折叠得出。

```
simple_demo_chain_version/executables/
├── main_logic/            # main_integrated.cpp / main_request_generator.cpp / main_request_placer.cpp
├── print_chain/           # 读取链并打印（回测视角）
├── single_pass/           # 单遍迭代模式
├── transcribe_chain/      # 链转录
├── enable_client/         # 使能客户端
├── enable_server/         # 使能服务端
├── calculator/            # 计算服务
├── data_source/           # 数据源
└── place_request/         # 下单请求
```

**关键看点**：
- `print_chain/main.cpp:36–49` —— `SharedChainCreator::readerFactory` 创建链数据源
- `print_chain/main.cpp:51–60` —— `setupExitTimer` 在 `SinglePassIterationApp` 中保障退出

对应文档：[tm_basic/08](tm_basic/08-shared-chain.md)、[tm_transport/04](tm_transport/04-shared-chains.md)、[tm_basic/10](tm_basic/10-app-runner-utils.md)

### `db_subscription/` — transaction v2 服务端/客户端

| 文件 | 角色 |
|---|---|
| `DBSubscriptionServer.cpp` | 服务端：定义 `DI`/`TI`，`DSComponent`（从 SQLite 加载）、`THComponent`（事务逻辑），建立 `transactionLogicCombination` |
| `DBSubscriptionClient.cpp` | 客户端：`dataStreamClientCombination`，订阅并打印 `DI::FullUpdate` |
| `ReadOnlyDBServer.cpp` / `ReadOnlyDBClient.cpp` | 只读查询服务与客户端（gRPC `db_subscription/Readonly/Query`） |
| `VersionlessSubscriptionServer.cpp` / `VersionlessSubscriptionClient.cpp` | 不带版本号的订阅变体 |
| `dbData.proto` | 与外部 gRPC 客户端共享的 proto 定义 |

**关键看点**：`DBSubscriptionServer.cpp:31–43` 的 `DI`/`TI` 定义；`:49` 起 `DSComponent::initialize` 从数据库加载全量；`:88` 起 `THComponent` 用 `acquireLock`/`releaseLock` 包住 SQL 事务。

对应文档：[tm_basic/09](tm_basic/09-transaction.md)、[tm_transport/07](tm_transport/07-kv-store-components.md)

### `db_one_list_subscription/` — 命名值存储与多路暴露

事务模型的轻量变体（`named_value_store`），并有 GUI 客户端。

```
db_one_list_subscription/
├── DBOneListSubscriptionServer.cpp    # 一个 facility 同时暴露到 RabbitMQ / gRPC / WebSocket / 组播合成
├── ReadOnlyDBOneListServer.cpp        # PreloadAllReadonlyServer 全量预载查询
├── DBTableImporterExporterTest.cpp    # SOCI 表导入/导出（各种模式）
├── DBOneListSinglePassPrinter.cpp     # 回测视角
├── VersionlessSinglePassPrinter.cpp
├── DBOneListSubscriptionClient.cpp    # 客户端
├── VersionlessSubscriptionServer.cpp  # 无版本订阅服务端
├── gui_client/GuiClientDataFlow.cpp   # GUI 客户端数据流
├── versionless_gui_client/
├── web_root/                          # 前端静态资源
└── (dotnet / node / python / grpc 各语言客户端)
```

**关键看点**：
- `DBOneListSubscriptionServer.cpp:280–330` —— 同一个 facility 用**四种方式**暴露（含 `SyntheticMultiTransportFacility` 在组播上合成）
- `ReadOnlyDBOneListServer.cpp:81–86` —— `PreloadAllReadonlyServer::fullDataQueryFacility`
- `DBTableImporterExporterTest.cpp:55–190` —— DB 表读写的全部模式（一次性/周期/带去重/单条/批量）

对应文档：[tm_basic/09](tm_basic/09-transaction.md)、[tm_transport/02](tm_transport/02-facilities.md)、[07](tm_transport/07-kv-store-components.md)

### `transaction_redundancy_test/` — 事务冗余

演示事务的双向/反向广播与冗余处理。

`TransactionReverseBroadcastServer.cpp`、`UserInputHandler.cpp`、`UserInputReverseBroadcastHandler.cpp` 等。

对应文档：[tm_basic/09](tm_basic/09-transaction.md)

### `common_flow_util_tests/` — 流处理工具集

`CommonFlowUtils` 与 `AppRunnerUtils` 的测试集合，是查"某个工具函数怎么用"的最快路径。

| 文件 | 演示 |
|---|---|
| `Synchronizer2Test.cpp` | `synchronizer2` / `snapshotOnRight` 等同步合并 |
| `TwoRunnerTest.cpp` | `MultiAppRunnerUtilComponents::run` 交错跑两个 runner |
| 其他 | 各类窗口、批处理、`bunchWith` 等 |

**关键看点**：`TwoRunnerTest.cpp:95–103` —— 用 `triggerImporterWithTime` 建"虫洞"跨 runner 传数据，再 `MultiAppRunnerUtilComponents::run(r1, r2)`。

对应文档：[tm_basic/05](tm_basic/05-common-flow-util.md)、[tm_basic/10](tm_basic/10-app-runner-utils.md)

### `serialization_test/` — 序列化

| 文件 | 演示 |
|---|---|
| `FixedPrecisionDecimalTest.cpp` | `FixedPrecisionShortDecimal` 的 CBOR/JSON/Proto 三格式编解码与精度转换 |

对应文档：[tm_basic/03](tm_basic/03-serialization.md)、[tm_basic/06](tm_basic/06-value-types.md)

### `clock_logic_test/` — 时钟与定时

`ClockLogicMain.hpp`、`timeout_test.cpp` 等，演示时钟 importer、超时、`AppClockHelper` 的用法。

对应文档：[tm_basic/01](tm_basic/01-clocks.md)

### `transport_utils/` — 传输工具

`byte_data_chain_transcriber.cpp`、`historical_republisher.cpp` 等，演示字节流录制/重放与历史数据重发。

对应文档：[tm_transport/00](tm_transport/00-overview.md)

> ⚠️ `historical_republisher.cpp:295` 使用了 `RequireMask` / `FanInParamMask`，这两个符号在 `tm_infra`/`tm_basic`/`tm_transport` 中**均无定义**——该文件应当编译不过，或对应仓库之外的版本。详见 [tm_infra/09](tm_infra/09-generated-pieces.md) 的说明。

### `websocket_test/`、`json_rest_test/`、`grpc_interop_test/`、`rpc_examples/`

四个传输专项测试。分别演示 WebSocket、JSON REST、gRPC、通用 RPC 的客户端与服务端。

对应文档：[tm_transport/03-transports/](tm_transport/03-transports/)

### `shared_chain_test/` — 链测试

对应文档：[tm_basic/08](tm_basic/08-shared-chain.md)

### `csv_test/`、`hdf5_test/` — 批量 I/O

对应文档：[tm_basic/07](tm_basic/07-csv-hdf5-flatpack.md)

### `synthetic_facility_test/` — 合成设施

对应文档：[tm_transport/02](tm_transport/02-facilities.md)

### `bcl_compat_test/` — .NET 兼容类型

演示 `tm_kit/transport/bcl_compat/` 下的 `Guid`、`Decimal`、`DateTime`、`Duration` 等与 C# BCL 对齐的类型。用于与 .NET 端互操作。

对应文档：[tm_transport/03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md)

### `prebuild/`、`external/`

非示例：`prebuild/` 放预构建工具，`external/` 放外部依赖的源码（如 certify）。

## 3. 推荐的阅读顺序

1. **`simple_demo/plain_executables/`** —— 先建立"实时/回测双模"的整体认知
2. **`common_flow_util_tests/`** —— 补上流处理工具的用法
3. **`db_subscription/`** —— 学 transaction v2（服务端 + 客户端）
4. **`simple_demo_chain_version/`** —— 学事件溯源与链
5. **`transport_utils/` + 传输专项测试** —— 按需深入某个传输

## 4. 相关章节

- [README](README.md) — 全套文档的入口与索引
- [QUICK_START](QUICK_START.md) — 从零写第一个程序
- [PATTERNS](PATTERNS.md) — 跨库模式与易错点
- [构建](BUILD.md) — 如何构建示例
