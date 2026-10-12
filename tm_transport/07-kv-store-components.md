---
title: 键值存储组件
library: tm_transport
headers: [tm_kit/transport/complex_key_value_store_components/OnDemandReadonlyServer.hpp, tm_kit/transport/complex_key_value_store_components/PreloadAllReadonlyServer.hpp, tm_kit/transport/complex_key_value_store_components/SingleTablePerItemTransactionServer.hpp, tm_kit/transport/complex_key_value_store_components/SingleTableAsCollectionTransactionServer.hpp, tm_kit/transport/named_value_store_components/NamedValueStoreConsumerCombination.hpp, tm_kit/transport/named_value_store_components/EtcdNamedValueStoreComponents.hpp, tm_kit/transport/named_value_store_components/EtcdLocalImporter.hpp, tm_kit/transport/named_value_store_components/EtcdHelper.hpp, tm_kit/transport/db_table_importer_exporter/DBTableImporterFactory.hpp, tm_kit/transport/db_table_importer_exporter/DBTableExporterFactory.hpp]
keywords: [complex_key_value_store_components, named_value_store_components, db_table_importer_exporter, OnDemandReadonlyServer, PreloadAllReadonlyServer, SingleTablePerItemTransactionServer, SingleTableAsCollectionTransactionServer, NamedValueStoreConsumerCombination, EtcdNamedValueStoreComponents, EtcdLocalImporter, EtcdHelper, DBTableImporterFactory, DBTableExporterFactory, StructFieldInfoUtils_SociHelper, 键值存储, 数据库表, SOCI, 只读查询, 事务服务]
---

# 键值存储组件

## 用途

本章覆盖三组"把外部存储接到数据流图"的组件：

1. **`complex_key_value_store_components`** —— 把数据库表当作键值存储：
   - `OnDemandReadonlyServer` / `PreloadAllReadonlyServer` —— 只读查询服务（按需查 / 全量预载）
   - `SingleTablePerItemTransactionServer` / `SingleTableAsCollectionTransactionServer` —— 基于数据库表的 **transaction v2 服务端**实现
2. **`named_value_store_components`** —— `tm_basic` 的 `named_value_store`（见 [transaction v2](../tm_basic/09-transaction.md)）的 **Etcd 后端**与消费端组合
3. **`db_table_importer_exporter`** —— 基于 **SOCI** 的数据库表导入器/导出器工厂

三者的分工：第 1、2 组是"有订阅/事务语义的服务"，第 3 组是"简单的批量读写节点"。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/complex_key_value_store_components/OnDemandReadonlyServer.hpp>
#include <tm_kit/transport/complex_key_value_store_components/PreloadAllReadonlyServer.hpp>
#include <tm_kit/transport/complex_key_value_store_components/SingleTablePerItemTransactionServer.hpp>
#include <tm_kit/transport/complex_key_value_store_components/SingleTableAsCollectionTransactionServer.hpp>
#include <tm_kit/transport/named_value_store_components/NamedValueStoreConsumerCombination.hpp>
#include <tm_kit/transport/named_value_store_components/EtcdNamedValueStoreComponents.hpp>
#include <tm_kit/transport/db_table_importer_exporter/DBTableImporterFactory.hpp>
#include <tm_kit/transport/db_table_importer_exporter/DBTableExporterFactory.hpp>

namespace dev::cd606::tm::transport::complex_key_value_store_components
namespace dev::cd606::tm::transport::named_value_store_components
namespace dev::cd606::tm::transport::db_table_importer_exporter
```

## 核心类型与签名

### 1. 只读查询服务（`complex_key_value_store_components`）

#### `PreloadAllReadonlyServer<M>`（`PreloadAllReadonlyServer.hpp:19`）

启动时把整张表读进内存，之后所有查询走内存。

```cpp
template <class ItemKey, class ItemData>
static auto keyBasedQueryFunc(...);                     // :21

template <class ItemKey, class ItemData>
static auto keyBasedQueryFacility(...);                 // :38

template <class ItemKey, class ItemData, class QueryType = basic::VoidStruct>
static auto fullDataQueryFacility(...);                 // :75
```

#### `OnDemandReadonlyServer<M>`（`OnDemandReadonlyServer.hpp:19`）

不预载，每次查询打到数据库。

```cpp
template <class ItemKey, class ItemData>
static auto keyBasedQueryFunc(...);                     // :58

template <class ItemKey, class ItemData, class QueryType = basic::VoidStruct>
static auto fullDataQueryFacility(...);                 // :137
```

**选择依据**：表小且查询频繁 → `PreloadAll`；表大或查询稀疏 → `OnDemand`（`PreloadAll` 会把整表塞进内存，大表会 OOM）。

### 2. 数据库表事务服务（`complex_key_value_store_components`）

这是一组把 `transaction::v2` 的服务端逻辑（见 [transaction v2](../tm_basic/09-transaction.md)）**落在数据库表上**的实现。两个变体：

| 类 | 表的语义 | 头文件 |
|---|---|---|
| `SingleTablePerItemTransactionServer<ItemKey,ItemData>` | **每行一个 item**（key 是主键列） | `SingleTablePerItemTransactionServer.hpp:18` |
| `SingleTableAsCollectionTransactionServer<ItemKey,ItemData>` | **一张表当作一个集合** | `SingleTableAsCollectionTransactionServer.hpp:20` |

两者都提供：

```cpp
// 内部类（继承 transaction v2 的组件接口）
template <class IDType>
class DSComponent : public basic::transaction::v2::DataStreamEnvComponent<DI>;   // PerItem:28 / AsCollection:30
template <class IDType>
class THComponent : public basic::transaction::v2::TransactionEnvComponent<TI>;  // PerItem:84 / AsCollection:90

// 初始化环境（注入 SOCI session 与表名）
// PerItem:290 / AsCollection:283
template <class Env, typename = std::enable_if_t<
    std::is_convertible_v<Env *, DSComponent *> && std::is_convertible_v<Env *, THComponent *>>>
static void initializeEnvironment(
    Env *env
    , std::shared_ptr<soci::session> const &session
    , std::string const &tableName
    , std::function<bool(std::string const &)> accountFilter = {}      // 账号过滤
    , std::optional<std::string> const &whereClause = std::nullopt     // 额外的 WHERE 子句
);

// 建立事务服务（内部调用 transactionLogicCombination）
// PerItem:322 / AsCollection:315
template <class R, typename = std::enable_if_t<...>>
static auto setupTransactionServer(
    R &r
    , std::string const &prefix
    , bool sealTransactionFacility = false
);
```

`setupTransactionServer` 内部创建的是 `basic::transaction::v2::transactionLogicCombination<R, TI, DI, DM, SubscriptionLoggingLevel::Verbose>`（`SingleTableAsCollectionTransactionServer.hpp:329` 附近），其中 `DM` 是 `complex_key_value_store::as_collection::DM<M, ItemKey, ItemData>`。

### 3. Etcd 命名值存储（`named_value_store_components`）

`tm_basic` 的 `named_value_store` 定义了 `DI<Data>` / `TI<Data>` / `GS<ID,Data>` 三件套（见 [transaction v2](../tm_basic/09-transaction.md)），这里给出 **Etcd 后端**的实现。

```cpp
// EtcdNamedValueStoreComponents.hpp:22 / :275
template <class Data>
class DSComponent : public basic::transaction::current::DataStreamEnvComponent<...>;  // :23
enum class LockChoice { /* ... */ };                                                  // :270
template <class Data>
class THComponent : public basic::transaction::current::TransactionEnvComponent<...>;  // :276
```

> 这里的 `basic::transaction::current` **就是 `v2` 的别名**——`tm_basic/tm_kit/basic/transaction/TransactionClient.hpp:14` 有 `namespace current = v2;`。所以 Etcd 命名值存储用的就是 [transaction v2](../tm_basic/09-transaction.md) 的接口，可以直接与 v2 的服务端组合（`transactionLogicCombination` 等）配套使用。

配套：

- `EtcdLocalImporter.hpp` —— 从本地 Etcd 读取的导入器
- `EtcdHelper.hpp` —— Etcd 连接辅助
- `etcd_lock_helper/` —— 基于 Etcd 的分布式锁
- `NamedValueStoreConsumerCombination.hpp:40` —— 消费端组合，`template <class R, typename Data>`；`:110`/`:125` 提供了带 `ProtocolWrapper` 的重载用于跨传输

### 4. 数据库表导入导出（`db_table_importer_exporter`）

基于 **SOCI** 的简单读写节点。**要求数据结构有 `StructFieldInfo` 反射**（`DBTableImporterFactory.hpp:59` 的 `enable_if` 要求 `basic::StructFieldInfo<T>::HasGeneratedStructFieldInfo`）。

```cpp
// DBTableImporterFactory.hpp:15
template <class M>
class DBTableImporterFactory {
public:
    // :61 — 一次性读完，返回 vector<T>
    template <class T, typename = std::enable_if_t<basic::StructFieldInfo<T>::HasGeneratedStructFieldInfo>>
    static auto getTableData(std::shared_ptr<soci::session> const &session, std::string const &importerInput)
        -> std::vector<T>;

    // :169 — 导入器节点
    template <class T, ...>
    static auto createImporter(std::shared_ptr<soci::session> const &session, std::string const &importerInput);

    // :198 — 周期性重新查询
    template <class T, ...>
    static auto createRepeatedImporter(
        std::shared_ptr<soci::session> const &session
        , std::string const &importerInput
        , std::chrono::system_clock::duration const &interval
    );

    // :237 — 周期性查询 + 按 key 去重（只发出新增行）
    template <class T, class KeyExtractor, ...>
    static auto createRepeatedImporterWithKeyCheck(
        std::shared_ptr<soci::session> const &session
        , std::string const &importerInput
        , std::chrono::system_clock::duration const &interval
        , KeyExtractor &&keyExtractor
    );

    // :380 — 按 key 查询
    template <class Key, class Data, ...>
    static auto queryTableData(
        std::shared_ptr<soci::session> const &session
        , std::string const &tableName
        , Key const &key
    ) -> std::vector<Data>;
};

// DBTableExporterFactory.hpp:16
template <class M>
class DBTableExporterFactory {
public:
    // :194 — 单条插入
    template <class T, ...>
    static auto createExporter(std::shared_ptr<soci::session> const &session, std::string const &tableName);

    // :217 — 插入前查重
    template <class T, ...>
    static auto createExporterWithDuplicateCheck(std::shared_ptr<soci::session> const &session, std::string const &tableName);

    // :241 — 批量插入（输入 vector<T>）
    template <class T, ...>
    static auto createBatchExporter(std::shared_ptr<soci::session> const &session, std::string const &tableName);
};
```

#### `importerInput` 的三种写法

`selectStatement_internal`（`DBTableImporterFactory.hpp:33`）按前缀决定如何处理：

| 写法 | 生成的 SQL |
|---|---|
| `"SELECT ..."` | 原样使用 |
| `"FROM ..."` | 在前面拼上 `SELECT <字段列表> ` |
| 其他 | 拼成 `SELECT <字段列表> FROM <输入>` |

所以 `"test_table"`、`"FROM test_table"`、`"SELECT name, value FROM test_table"` 都合法。

#### 后端适配

`selectStatement`（`:47`）按 `session->get_backend_name()` 选择 trait：

- `"mysql"` → `db_traits::MysqlTraits`
- `"sqlite3"` → `db_traits::Sqlite3Traits`
- 其他 → 默认 trait

字段名转换与取值逻辑在 `StructFieldInfoUtils_SociHelper.hpp` 中。

## 最小可用示例

### 只读查询服务：全量预载

来源：`tm_examples/db_one_list_subscription/ReadOnlyDBOneListServer.cpp:73–86`

```cpp
auto session = std::make_shared<soci::session>(
    soci::sqlite3
    , vm["db_file"].as<std::string>()
);

auto queryFacility = transport::complex_key_value_store_components::PreloadAllReadonlyServer<M>
    ::fullDataQueryFacility<DBKey, DBData>
    (
        session
        , "FROM test_table"
    );
```

同一文件的 `:88` 附近注释掉了 `OnDemandReadonlyServer` 的等价写法（`OnDemandReadonlyServer<M>::fullDataQueryFacility<DBKey, DBData>(...)`），可作为两种模式切换的对照。

### 数据库表导入器

来源：`tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:55–75`（已简化）

```cpp
// 一次性读完
infra::DeclarativeGraph<R>("", {
    {"importer", transport::db_table_importer_exporter::DBTableImporterFactory<M>
        ::createImporter<test_data>(session, "test_table")}
    , {"dispatch", basic::CommonFlowUtilComponents<M>::dispatchOneByOne<test_data>()}
    , {"print", [&env](test_data &&x) { /* ... */ }}
    , infra::DeclarativeGraphChain({"importer", "dispatch", "print"})
})(r);

// 每秒重新查询，输出 vector<test_data>
{"importer", transport::db_table_importer_exporter::DBTableImporterFactory<M>
    ::createRepeatedImporter<test_data>(session, "test_table", std::chrono::seconds(1))}

// 每秒查询 + 按 key 去重（只发新增行）
{"importer", transport::db_table_importer_exporter::DBTableImporterFactory<M>
    ::createRepeatedImporterWithKeyCheck<test_data>(
        session
        , "test_table"
        , std::chrono::seconds(1)
        , [](test_data const &x) { return x.name; }   // key 提取器
    )}
```

### 数据库表导出器

来源：`tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:118–137`（已简化）

```cpp
// 单条插入
{"insert", transport::db_table_importer_exporter::DBTableExporterFactory<M>
    ::createExporter<test_data>(session, "test_table")}

// 批量插入（输入是 vector<test_data>）
{"insert", transport::db_table_importer_exporter::DBTableExporterFactory<M>
    ::createBatchExporter<test_data>(session, "test_table")}
```

`createBatchExporter` 的输入类型是 `vector<T>`，因此在 `DeclarativeGraph` 里常与 `constFirstPushImporter<vector<test_data>>` 或 `bunchWith` 配合，不需要中间的 `dispatchOneByOne`。

## 实时 / 回测行为差异

| 组件 | 实时 | 回测 |
|---|---|---|
| `PreloadAllReadonlyServer` | 启动时预载，之后内存查询 | 同样可用，且更合适（表数据固定，不随"当下"变化） |
| `OnDemandReadonlyServer` | 每次查询打数据库 | **不适用**——查询返回的是"现在"的表状态，不是回测时点的状态 |
| `SingleTable*TransactionServer` | 真实写入数据库表 | 回测通常只读；需要写入语义时应用内存实现（`as_collection::DM` / transaction v2 的默认 `TransactionDataStore`） |
| `EtcdNamedValueStoreComponents` | 跨进程共享状态 | 不适用 |
| `DBTableImporterFactory` | 可用；`createRepeated*` 靠墙钟驱动 | **推荐**：`createImporter` 一次性读入，数据固定 |
| `DBTableExporterFactory` | 写数据库 | 通常不写，或写到独立的结果表 |

**回测的关键约束**：数据库表是**可变状态**，回测读到的是"当前"值而非"当时"值。要在回测中复现历史，必须：

- 用**带时间列**的表，并在查询里加 `WHERE time <= <回测时点>`（`whereClause` 参数就是为此设计的，见 `initializeEnvironment`）
- 或者把实时阶段的数据快照成**不可变的历史文件**，回测只读文件

`SingleTablePerItemTransactionServer::initializeEnvironment` 的 `whereClause` 参数（`SingleTablePerItemTransactionServer.hpp:290`）正是用来给事务服务加上时点过滤的。

## 易错点

**1. `DBTableImporterFactory` 要求 `StructFieldInfo` 反射**

`enable_if` 条件 `basic::StructFieldInfo<T>::HasGeneratedStructFieldInfo`（`DBTableImporterFactory.hpp:59`）。只定义了普通 struct 而没有加 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE` 之类宏的类型不能用于 DB 读写。这与 [CSV/HDF5](../tm_basic/07-csv-hdf5-flatpack.md) 的要求一致。

**2. `PreloadAllReadonlyServer` 在启动时把整表读进内存**

大表（百万行以上）会导致启动慢 + 内存暴涨。表会增长的生产环境应改用 `OnDemandReadonlyServer`，或给 `PreloadAll` 加 `whereClause` 限制范围。

**3. `createRepeatedImporter` 靠墙钟驱动，回测中语义错误**

它按 `interval`（墙钟）周期性重查数据库。回测中"周期"应当由**数据时间**驱动而非墙钟——用 `createRepeatedImporter` 会让回测的查询节奏与实际历史无关。回测请用一次性 `createImporter`。

**4. `createRepeatedImporterWithKeyCheck` 的 key 提取器必须是稳定的业务主键**

`KeyExtractor`（`DBTableImporterFactory.hpp:237`）从行里提取去重键。用会变化的字段（如带时间戳的列）做 key 会导致每轮都认为全是新行。用行的稳定业务主键。

**5. `importerInput` 的三种写法靠字符串前缀判断**

`selectStatement_internal`（`:33`）用 `boost::to_upper_copy` 后判断前缀。因此 `"select ..."`（小写）不会走"原样使用"分支，而会被当作表名拼成 `SELECT <fields> FROM select ...`，产生 SQL 语法错误。**SQL 关键字必须大写**。

**6. `transaction::current` 是 `v2` 的别名，不是另一套接口**

`EtcdNamedValueStoreComponents.hpp:23`、`:276` 用的 `basic::transaction::current::` 会让人以为存在"current"和"v2"两套 API。实际上 `tm_basic/tm_kit/basic/transaction/TransactionClient.hpp:14` 只有一行 `namespace current = v2;`——两者完全等价。不必为"选哪个"纠结，也不要试图找 `current` 的独立文档。

**7. `setupTransactionServer` 需要先 `initializeEnvironment`**

`initializeEnvironment` 把 SOCI session 与表名注入 Environment；`setupTransactionServer` 只是建图。顺序颠倒会得到空 session 导致的运行期崩溃。两者的 `enable_if` 都要求 Environment 已包含 `DSComponent`/`THComponent`——所以 `initializeEnvironment` 必须在**实例化 `TheEnvironment` 类型时**就把这两个组件列进去。

**8. SOCI 的 `session` 必须活得比图长**

`std::shared_ptr<soci::session>` 被组件持有（`SingleTableAsCollectionTransactionServer.hpp:289` 的参数就是 shared_ptr）。如果 session 在 `AppRunner` 析构前被释放，会出现悬空引用。示例统一用 `std::make_shared<soci::session>` 并在 `main` 作用域持有。

**9. 多线程下 SOCI session 不是线程安全的**

SOCI 的 `session` 对象**不可跨线程共享**。在 `RealTimeApp`（多线程）下，同一个 session 被导入器与导出器同时使用会产生数据竞争。需要为每个线程/每个组件单独的 session，或在外层加重试与互斥。

**10. `SingleTablePerItem` 与 `SingleTableAsCollection` 的表结构约定不同**

前者要求表的主键列对应 `ItemKey`，一行一个 item；后者把整张表视为一个集合。选错会导致 key 映射错位（不报错，只是数据语义不对）。用之前先确认表结构。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| SOCI | `soci` | 数据库访问抽象（sqlite3 / mysql / odbc / postgresql） | https://soci.sourceforge.net/ |
| sqlite3 | 由 SOCI 传递依赖 | SQLite 后端 | https://www.sqlite.org/ |
| MySQL client | 由 SOCI 传递依赖 | MySQL 后端 | https://dev.mysql.com/doc/c-api/ |
| PostgreSQL libpq | 由 SOCI 传递依赖 | PostgreSQL 后端 | https://www.postgresql.org/docs/current/libpq.html |
| unixODBC / libltdl | 由 SOCI 传递依赖 | ODBC 后端 | https://www.unixodbc.org/ |
| etcd-cpp-apiv3 | `libetcdcpp` | Etcd 命名值存储 | https://github.com/etcd-cpp-apiv3/etcd-cpp-apiv3 |
| gRPC | `grpc` | Etcd 客户端的传输层 | https://grpc.io/docs/languages/cpp/ |

`tm_transport/meson.build:13` 声明 `soci_dep = dependency('soci')`，`:12` 声明 `etcd_dep = dependency('libetcdcpp')`。

> ⚠️ **本环境的 `.pc` 修补（两处，都与本章直接相关）**：
>
> 1. **`soci.pc` 是从零创建的**（SOCI 4.1.4 只提供 CMake config，没有 pkg-config 文件）。内容是 `Requires: fmt odbc mysqlclient`，`Libs: -lsoci_sqlite3 -lsoci_mysql -lsoci_odbc -lsoci_postgresql -lsoci_core -lsqlite3 -lpq`。
> 2. **`odbc.pc` 的 `-lltdl` 改为绝对路径 `${libdir}/libltdl.a`**，因为 meson 的 `--as-needed` 会丢弃 `-l` 形式的 libltdl。
>
> **教训**（同样适用于为 SOCI 写 `.pc`）：传递依赖要放在 `Requires:` 而不是 `Libs:`——只有 `Requires:` 才会让 pkg-config 展开该库自身的依赖链（这正是 `mysql.h` 的 include 路径 `include/mysql` 能被找到的原因）。详见仓库根 `CLAUDE.md` 的 "Known Build Issues & Fixes" 第 3、5 条。

**任何 `.pc` 的修改都需要完整重配置**（meson 在 configure 阶段缓存依赖信息），即 `build.sh` 里选 "clean rebuild"。

## 相关章节

- [transaction v2](../tm_basic/09-transaction.md) — `DataStreamEnvComponent`、`TransactionEnvComponent`、`transactionLogicCombination`、`named_value_store`
- [CSV / HDF5 / FlatPack](../tm_basic/07-csv-hdf5-flatpack.md) — 文件形式的批量 I/O，与 DB 表读写是互补方案
- [序列化宏与结构反射](../tm_basic/02-struct-field-info.md) — `StructFieldInfo<T>` 是本章所有组件的前提
- [共享链后端](04-shared-chains.md) — 另一种状态持久化方案（append-only 日志，适合事件溯源）
- [远程设施](02-facilities.md) — 把本章的事务服务暴露到网络
- [tm_transport 概览](00-overview.md) — 组件模型与依赖链
