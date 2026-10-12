# tm_kit 开发文档 — Agent 索引

**tm_kit 是一套 C++17 数据流框架**，由三个库组成，让同一份业务逻辑既能在实时（`RealTimeApp`，多线程、挂钟驱动）下运行，也能在回测（`SinglePassIterationApp` / `TopDownSinglePassIterationApp`，单线程、数据驱动）下运行。

```
tm_infra  ──►  tm_basic  ──►  tm_transport
  图与节点       时钟/序列化/事务     进程间通信
```

完整参考文档 {{DOC_COUNT}} 篇、约 {{LINE_COUNT}} 行，就在本仓库里。单篇 3k–14k token，**整包约 38 万 token，不要一次性全读**。

## 怎么用这套文档

三层，按需升级：

| 层 | 内容 | 什么时候用 |
|---|---|---|
| **常驻** | 就是本文件 | 每次会话自动加载。铁律 + 路由表足够覆盖大部分情况 |
| **单篇** | {{DOC_COUNT}} 篇文档文件 | 要写某类代码时，按下面的路由表或关键词索引定位，然后整篇 Read |
| **检索** | `tools/tm_docs` | 路由表里找不到时用它搜；比盲 grep 准 |

```bash
# 按关键词 / 任务描述搜（返回命中文件与片段）
./tools/tm_docs find "事务 订阅"
./tools/tm_docs find --task "跨进程发请求收响应"

# 手里有个 #include，想知道它归哪篇文档管
./tools/tm_docs headers CommonFlowUtils.hpp

# 直接打印一篇（或其中一节）
./tools/tm_docs show tm_basic/09-transaction
./tools/tm_docs show tm_basic/09-transaction --section 易错点

# 只看路由表（不加载全文）
./tools/tm_docs index
```

不用 CLI 也行：每篇的 YAML front-matter 里有 `headers`（覆盖哪些头文件）和 `keywords`，`grep -rl "<关键字>" tm_kit_reference/` 同样有效。

## 铁律

**下面每条都会导致静默错误或难以定位的编译错误。写 tm_kit 代码前先过一遍。**

1. **业务逻辑必须对 App 类型 `M` 模板化。** 写死 `using M = infra::RealTimeApp<Env>` 会让代码无法在回测下复用。正确做法是把 `M`/`R` 作为模板参数传进业务组合函数。

2. **回测没有 `r.run()`。** `SinglePassIterationApp` 的整遍迭代在 `AppRunner::finalize()` 内部执行完就返回；实时模式的 `finalize()` 则是启动线程后立即返回，必须靠 `terminationController(...)` 阻塞住 main，否则进程直接退出。

3. **传输节点硬编码 `RealTimeApp`。** `MultiTransportBroadcastListener` / `MultiTransportRemoteFacility` 放进单遍迭代 App 会得到一大片模板实例化错误。回测要么读文件，要么用本地 mock facility 顶上同一个 `FacilitioidConnector` 变量。

4. **`Source` 只能 `std::move` 一次。** 一个 source 接多个 sink 时，前 N-1 次必须用 `source.clone()`，最后一次才 `std::move`。用两次 `std::move` 会抛 `Source is not initialized.`——这是组图代码里最高频的错误。

5. **facility 的输出默认只允许 1 个下游连接。** 要让一个 facility 服务多个调用方（多个 wrapper），必须先 `r.setMaxOutputConnectivity(facility, n)`，否则 `finalize()` 报连通度超限。

6. **节点用 `.get()` 捕获的 `shared_ptr` 必须 `r.preservePointer(ptr)`。** 组图函数返回后局部 `shared_ptr` 即析构，裸指针悬垂——**这是组图时最容易写出的 use-after-free**。

7. **只有用反射宏生成的结构体才有 `StructFieldInfo`。** CSV / HDF5 / FlatPack 读写、`DBTableImporterFactory`、gRPC interop 全都要求它。裸 `struct Foo {...};` 会在某个 `enable_if` 处失败，报错信息不直观。序列化还需额外加 `_SERIALIZE` 宏。

8. **`WireToUserHook` 失败是静默的。** 验签/解密失败返回 `nullopt`，消息被丢弃，**无日志无异常**。"心跳或数据莫名收不到"时，先查 hook 配置（密钥、name tag）是否两端匹配。

9. **`finalFlag` 漏发会让回测永不结束。** 单遍迭代模式下游靠它停止拉取。自定义 importer 必须在数据耗尽时发一个带 final 标记的数据包——表现为程序挂住不退出、CPU 空转。

10. **心跳周期必须小于客户端的 `ttl`。** 服务端 `attachHeartbeatAndAlertComponent(period)` 的 period 若大于客户端 `ttl`（默认 3 秒），服务会被误判为下线。另外 `furthestPoint` **默认只有 24 小时**，长跑程序到点后心跳静默停止。

11. **实时/回测的时间来源必须一致地走环境。** 业务代码里直接调 `std::chrono::system_clock::now()` 会让回测结果依赖运行时刻，彻底破坏可重放性。用 `env->now()` / `env->resolveTime()`。

12. **`CheckTimeComponent<false>` 不会关掉版本检查。** 时间倒流检查与 `VersionChecker` 是两套独立机制，后者无条件生效，会把版本不前进的数据静默丢弃。

## 按任务查

写代码前先在这里定位，然后整篇 Read 那一篇。

| 我要…… | 看 |
|---|---|
| 写第一个程序 / 搭实时+回测双模骨架 | `QUICK_START.md` |
| 排查"为什么会这样" / 跨模块坑 | `PATTERNS.md` |
| 选 App 类型（实时 vs 回测） | `tm_infra/01-app-types.md` |
| 写节点：liftPure / liftMaybe / kleisli | `tm_infra/03-nodes-and-lifting.md` |
| 请求-响应：facility 四变体 | `tm_infra/04-facilities.md` |
| 组图：register / connect / finalize | `tm_infra/05-app-runner.md` |
| 声明式建图 DeclarativeGraph | `tm_infra/06-declarative-graph.md` |
| 时间戳、finalFlag、版本检查 | `tm_infra/07-time-and-data.md` |
| Environment 里放哪些组件 | `tm_infra/02-environments.md` |
| 定义结构体 + 反射宏 | `tm_basic/02-struct-field-info.md` |
| 选序列化格式（CBOR / Proto / JSON） | `tm_basic/03-serialization.md` |
| 表示价格、日期、编译期常量 | `tm_basic/06-value-types.md` |
| 滑动窗口 / 批处理 / 同步合并 | `tm_basic/05-common-flow-util.md` |
| CSV / HDF5 / 动态字段访问 | `tm_basic/07-csv-hdf5-flatpack.md` |
| 事务型状态服务（带订阅） | `tm_basic/09-transaction.md` |
| 事件溯源 / 可重放状态机 | `tm_basic/08-shared-chain.md` |
| 多图交错回测 / 退出计时器 | `tm_basic/10-app-runner-utils.md` |
| 时钟组件怎么选 | `tm_basic/01-clocks.md` |
| 跨进程广播 / 发布订阅 | `tm_transport/01-broadcast.md` |
| 跨进程 RPC / 远程设施 | `tm_transport/02-facilities.md` |
| 选传输（RabbitMQ / ZeroMQ / gRPC…） | `tm_transport/00-overview.md` + `tm_transport/03-transports/` |
| 服务发现 / 心跳 | `tm_transport/05-heartbeat-and-alert.md` |
| 签名 / 身份校验 / TLS | `tm_transport/06-security.md` |
| 数据库表当数据源 / 链后端 | `tm_transport/07-kv-store-components.md`、`tm_transport/04-shared-chains.md` |
| 找示例代码 | `EXAMPLES_MAP.md` |
| 依赖 / 链接报错 / `.pc` 修补 | `THIRD_PARTY.md` |
| 术语中英对照 | `GLOSSARY.md` |

## 实时 / 回测对照速查

| 维度 | 实时 `RealTimeApp` | 回测 `(TopDown)SinglePassIterationApp` |
|---|---|---|
| 时钟组件 | `basic::real_time_clock::ClockComponent` | `basic::(top_down_)single_pass_iteration_clock::ClockComponent` |
| 时间戳来源 | 挂钟 `now()`，与输入无关 | 触发它的输入的时间戳，并推进全局时钟 |
| `CheckTimeComponent` | `<false>`（网络乱序是常态） | `<true>`（数据应严格有序） |
| 退出控制 | `TrivialExitControlComponent` | `FlagExitControlComponent` |
| ID 生成 | `transport::BoostUUIDComponent`（跨进程唯一） | `basic::IntIDComponent<>`（可复现） |
| `SuggestThreaded` | 生效 | 忽略 |
| `DelaySimulator` | 忽略 | 生效（模拟逻辑耗时） |
| 结束方式 | `terminationController` 阻塞 main | `finalize()` 返回即结束 |
