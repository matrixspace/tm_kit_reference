---
title: Transaction v2 — 分布式事务与订阅框架
library: tm_basic
headers:
  - tm_kit/basic/transaction/v2/TransactionInterface.hpp
  - tm_kit/basic/transaction/v2/DataStreamInterface.hpp
  - tm_kit/basic/transaction/v2/TransactionFacility.hpp
  - tm_kit/basic/transaction/v2/GeneralSubscriber.hpp
  - tm_kit/basic/transaction/v2/TransactionDataStore.hpp
  - tm_kit/basic/transaction/v2/TransactionEnvComponent.hpp
  - tm_kit/basic/transaction/v2/DataStreamEnvComponent.hpp
  - tm_kit/basic/transaction/v2/TransactionLogicCombination.hpp
  - tm_kit/basic/transaction/v2/DataStreamClientCombination.hpp
  - tm_kit/basic/transaction/v2/TransactionDeltaMerger.hpp
  - tm_kit/basic/transaction/v2/DefaultUtilities.hpp
  - tm_kit/basic/transaction/named_value_store/DataModel.hpp
keywords:
  - TransactionInterface
  - DataStreamInterface
  - TransactionProcessor
  - GeneralSubscriber
  - TransactionDataStore
  - TransactionEnvComponent
  - DataStreamEnvComponent
  - transactionLogicCombination
  - dataStreamClientCombination
  - basicDataStreamClientCombination
  - TransactionDeltaMerger
  - RequestDecision
  - InsertAction
  - UpdateAction
  - DeleteAction
  - TransactionResponse
  - OneFullUpdateItem
  - OneDeltaUpdateItem
  - OneUpdateItem
  - FullUpdate
  - Update
  - GeneralSubscriberTypes
  - IGeneralSubscriber
  - ConstChecker
  - TriviallyMerge
  - TriviallyProcess
  - named_value_store
  - 分布式事务
  - 数据订阅
  - 乐观锁
---

# Transaction v2 — 分布式事务与订阅框架

## 用途

`transaction::v2` 提供一套完整的"键值存储 + 变更订阅"协议实现，适用于以下量化场景：

- **状态服务**：服务端维护一张按 Key 组织的数据表，多客户端订阅变更流并保持本地副本同步
- **分布式事务**：客户端以 Insert/Update/Delete 三种操作请求修改数据，服务端使用乐观锁检查版本一致性后提交并广播变更
- **回测重播**：相同的服务端逻辑可以在 `SinglePassIterationApp` 下无修改运行，变更流由 `DataStreamEnvComponent` 注入而非从网络接收

框架将服务端的"事务处理"与"变更广播+订阅管理"拆分为两个独立 facility，通过 `transactionLogicCombination` 组合后暴露给 `AppRunner`。

## 头文件与命名空间

```cpp
// 按依赖顺序包含（实际上 TransactionLogicCombination.hpp 已全部引入）
#include <tm_kit/basic/transaction/v2/TransactionLogicCombination.hpp>
#include <tm_kit/basic/transaction/v2/DataStreamClientCombination.hpp>

namespace dev::cd606::tm::basic::transaction::v2
```

快捷别名模型（`named_value_store` 子目录，`:1`）：

```cpp
#include <tm_kit/basic/transaction/named_value_store/DataModel.hpp>
// 提供 named_value_store::DI<Data>、TI<Data>、GS<ID,Data> 预绑定类型
```

## 核心类型与签名

### 1. `TransactionInterface<GV,K,V,D,...>` — 事务类型描述符（`:66`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionInterface.hpp:66
template <
    class GlobalVersionType          // 全局版本号类型（通常 int64_t）
    , class KeyType                  // 数据行的 Key 类型
    , class VersionType              // 行级版本类型
    , class DataType                 // 行数据类型
    , class DataSummaryType = DataType    // 摘要（供版本检查使用）
    , class VersionSliceType = VersionType
    , class DataDeltaType = DataType     // 增量类型（Update 的 payload）
    , class ProcessedUpdateType = DataDeltaType
>
class TransactionInterface {
public:
    using GlobalVersion = GlobalVersionType;
    using Key = KeyType;
    using Version = VersionType;
    using Data = DataType;
    using DataDelta = DataDeltaType;
    using ProcessedUpdate = ProcessedUpdateType;

    using InsertAction = transaction::v2::InsertAction<Key,Data>;        // :117
    using UpdateAction = transaction::v2::UpdateAction<Key,VersionSlice,DataSummary,DataDelta>; // :118
    using DeleteAction = transaction::v2::DeleteAction<Key,Version,DataSummary>; // :119

    // wire type：variant<Insert,Update,Delete> 包在 SingleLayerWrapper 中
    using Transaction = SingleLayerWrapper<std::variant<InsertAction,UpdateAction,DeleteAction>>;
    using TransactionResponse = transaction::v2::TransactionResponse<GlobalVersion>;

    // 实际入站类型：(account_string, Transaction)
    using TransactionWithAccountInfo = std::tuple<Account,Transaction>;
};
```

#### 操作结构（`:43–64`）

```cpp
// 插入：key + data，要求 key 不存在
template <class K, class D>
struct InsertAction { K key; D data; };

// 更新：key + 可选旧版本切片 + 可选旧数据摘要 + 数据增量
template <class K, class VS, class DS, class DD>
struct UpdateAction {
    K key;
    std::optional<VS> oldVersionSlice;
    std::optional<DS> oldDataSummary;
    DD dataDelta;
};

// 删除：key + 可选旧版本 + 可选旧数据摘要
template <class K, class V, class DS>
struct DeleteAction {
    K key;
    std::optional<V> oldVersion;
    std::optional<DS> oldDataSummary;
};

// 事务响应（`:61`）
template <class GV>
struct TransactionResponse {
    GV globalVersion;
    RequestDecision requestDecision;
};
```

#### `RequestDecision` 枚举（`:15`）

```cpp
enum class RequestDecision : int16_t {
    Success = 0
    , FailurePrecondition = 1   // key 不存在（insert）/ key 已存在（update/delete）
    , FailurePermission   = 2   // 账户权限不足
    , FailureConsistency  = 3   // 版本或摘要不匹配（乐观锁失败）
};
```

---

### 2. `DataStreamInterface<GV,K,V,D,...>` — 数据流类型描述符（`:24`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/DataStreamInterface.hpp:24
template <
    class GlobalVersionType
    , class KeyType
    , class VersionType
    , class DataType
    , class VersionDeltaType = VersionType
    , class DataDeltaType = DataType
    , class GlobalVersionCmp = std::less<GlobalVersionType>
    , class VersionCmp = std::less<VersionType>
>
class DataStreamInterface {
public:
    // 全量更新项：一个 Key 对应的当前完整值（版本 + 可选 Data）
    using OneFullUpdateItem = GroupedVersionedData<Key, Version, std::optional<Data>, VersionCmp>;  // :64

    // 增量更新项：(Key, VersionDelta, DataDelta)
    using OneDeltaUpdateItem = std::tuple<Key, VersionDelta, DataDelta>;  // :70

    // 统一的更新项（variant 包在 SingleLayerWrapper 中）
    using OneUpdateItem = SingleLayerWrapper<std::variant<OneFullUpdateItem, OneDeltaUpdateItem>>;  // :75

    // 一次更新推送（全局版本 + 若干 OneUpdateItem）
    using Update = VersionedData<GlobalVersion, std::vector<OneUpdateItem>, GlobalVersionCmp>;  // :79

    // 纯全量更新（供订阅快照使用，不含 OneDelta）
    using FullUpdate = VersionedData<GlobalVersion, std::vector<OneFullUpdateItem>, GlobalVersionCmp>;  // :85

    // 工具函数：从 Update 中过滤出仅包含全量项的 FullUpdate（:90）
    static FullUpdate getFullUpdatesOnly(Update const &);
};
```

---

### 3. `TransactionEnvComponent<TI>` — 事务逻辑插件接口（`:9`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionEnvComponent.hpp:9
template <class TI>
class TransactionEnvComponent {
public:
    // acquireLock / releaseLock 返回锁定时刻的全局版本号
    // dataDelta 可为 nullptr（仅做 key 级锁定时不提供）
    virtual typename TI::GlobalVersion acquireLock(
        std::string const &account,
        typename TI::Key const &key,
        typename TI::DataDelta const *dataDelta) = 0;
    virtual typename TI::GlobalVersion releaseLock(
        std::string const &account,
        typename TI::Key const &key,
        typename TI::DataDelta const *dataDelta) = 0;

    // 三种事务操作的实现（由用户提供，通常含数据库写入）
    virtual typename TI::TransactionResponse handleInsert(
        std::string const &account,
        typename TI::Key const &key,
        typename TI::Data const &data) = 0;
    virtual typename TI::TransactionResponse handleUpdate(
        std::string const &account,
        typename TI::Key const &key,
        std::optional<typename TI::VersionSlice> const &updateVersionSlice,
        typename TI::ProcessedUpdate const &processedUpdate) = 0;
    virtual typename TI::TransactionResponse handleDelete(
        std::string const &account,
        typename TI::Key const &key,
        std::optional<typename TI::Version> const &versionToDelete) = 0;
};
```

---

### 4. `DataStreamEnvComponent<DI>` — 数据流注入接口（`:9`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/DataStreamEnvComponent.hpp:9
template <class DI>
class DataStreamEnvComponent {
public:
    class Callback {
    public:
        virtual void onUpdate(typename DI::Update &&) = 0;
    };
    // initialize 在 DataStreamImporter::start() 调用时触发
    // 实现应当：读取初始状态并发出全量 Update，然后注册监听后续变更
    virtual void initialize(Callback *cb) = 0;
};
```

---

### 5. `TransactionDataStore<DI,KeyHash,MutexProtected>` — 内存数据仓库（`:14`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionDataStore.hpp:14
template <class DI, class KeyHashType = std::hash<typename DI::Key>, bool MutexProtected=true>
struct TransactionDataStore {
    using DataMap = std::unordered_map<
        typename DI::Key
        , VersionedData<typename DI::Version, std::optional<typename DI::Data>, typename DI::VersionCmp>
        , KeyHash
    >;

    mutable Mutex mutex_;      // std::mutex（MutexProtected=true）或 bool（=false）
    DataMap dataMap_;
    GlobalVersion globalVersion_;

    // 等待全局版本到达 v（忙等，实时模式下 TransactionProcessor 在 publishResponse 之后调用）
    void waitForGlobalVersion(typename DI::GlobalVersion const &v);

    // 从 dataMap_ 构造 FullUpdate（供 GeneralSubscriber 快照使用）
    typename DI::Update createFullUpdateNotification(std::vector<typename DI::Key> const &keys) const;
    typename DI::FullUpdate createFullUpdateNotificationWithoutVariant(std::vector<typename DI::Key> const &keys) const;
};

template <class DI, class KeyHash=std::hash<typename DI::Key>, bool MP=true>
using TransactionDataStorePtr = std::shared_ptr<TransactionDataStore<DI,KeyHash,MP>>;
```

---

### 6. `TransactionProcessor<M,TI,DI,...>` — 事务 facility 实现（`:46`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionFacility.hpp:46
template <
    class M, class TI, class DI
    , TransactionLoggingLevel TLogging = TransactionLoggingLevel::Verbose
    , class VersionChecker       = std::equal_to<typename TI::Version>
    , class VersionSliceChecker  = std::equal_to<typename TI::Version>
    , class DataSummaryChecker   = std::equal_to<typename TI::Data>
    , class DeltaProcessor       = TriviallyProcess<typename TI::Data, typename TI::DataDelta, typename TI::ProcessedUpdate>
    , class KeyHash = std::hash<typename DI::Key>
    , bool Silent = false
>
class TransactionProcessor
    : public ITransactionFacility<M,TI,DI,TLogging,KeyHash>  // 当 Silent=false
    , public M::IExternalComponent
{};
```

**约束**：`TI::GlobalVersion`、`TI::Key`、`TI::Version`、`TI::Data` 必须与 `DI` 对应类型完全一致（编译期 `static_assert`）。

`TransactionProcessor` 本身不含 Insert/Update/Delete 逻辑，只是框架"骨架"：
- 接收 `TI::TransactionWithAccountInfo`，调用环境组件 `TransactionEnvComponent<TI>` 的 `handleInsert/Update/Delete`
- 乐观锁检查由 `VersionChecker`、`VersionSliceChecker`、`DataSummaryChecker` 完成
- `DeltaProcessor` 将 `DataDelta` 转换为 `ProcessedUpdate`（默认直接透传）

多线程实时模式下，TransactionProcessor 使用双缓冲队列 + 后台事务线程串行处理请求（`:101`）。

接口层次（`:21–45`）：

```cpp
enum class TransactionLoggingLevel { None, Verbose };

// 抽象基：提供 dataStorePtr()
template <class M, class TI, class DI>
class ITransactionProcessorBase { public: virtual TransactionDataStorePtr<DI,...> dataStorePtr() = 0; };

// 作为 OnOrderFacilityWithExternalEffects（广播变更流）
template <class M, class TI, class DI, TransactionLoggingLevel L, class KeyHash>
class ITransactionFacility
    : public M::template AbstractOnOrderFacilityWithExternalEffects<
        typename TI::TransactionWithAccountInfo
        , typename TI::TransactionResponse
        , typename DI::Update
    >
    , public ITransactionProcessorBase<M,TI,DI>
{};

// Silent 版本：作为 Exporter（不发布响应）
template <class M, class TI, class DI, TransactionLoggingLevel L, class KeyHash>
class ISilentTransactionHandler
    : public M::template AbstractExporter<typename TI::TransactionWithAccountInfo>
    , public ITransactionProcessorBase<M,TI,DI>
{};
```

---

### 7. `GeneralSubscriberTypes<ID,DI>` — 订阅协议类型集（`:52`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/GeneralSubscriber.hpp:52
template <class IDType, class DI>
struct GeneralSubscriberTypes {
    // 订阅管理消息类型（:25-48）
    using Subscription    = struct { std::vector<typename DI::Key> keys; };
    using Unsubscription  = struct { IDType originalSubscriptionID; };
    using ListSubscriptions = struct {};
    using UnsubscribeAll  = struct {};
    using SnapshotRequest = struct { std::vector<typename DI::Key> keys; };

    // 订阅确认/通知消息类型
    using SubscriptionUpdate = typename DI::Update;  // 实际数据推送
    using SubscriptionInfo   = struct { IDType subscriptionID; std::vector<typename DI::Key> keys; };

    // 入站 variant：所有客户端请求类型
    using Input = SingleLayerWrapper<std::variant<
        Subscription, Unsubscription, ListSubscriptions, UnsubscribeAll, SnapshotRequest
    >>;

    // 出站 variant：所有服务端响应类型
    using Output = SingleLayerWrapper<std::variant<
        Subscription, Unsubscription, SubscriptionUpdate, SubscriptionInfo, UnsubscribeAll
    >>;

    // 带账号信息的入站类型（transport 层使用）
    using InputWithAccountInfo = std::tuple<std::string, Input>;
};
```

`GeneralSubscriber<M,DI,KeyHash,VerboseLogging>`（`:83`）是 `IGeneralSubscriber`（`AbstractIntegratedLocalOnOrderFacility`）的具体实现，内部维护：
- `subscriptionMap`: Key → 订阅该 Key 的 ID 集合
- `idInfoMap`: ID → 该 ID 订阅的 Key 集合

收到 `SubscriptionUpdate` 时向所有相关订阅者推送变更（实时模式加读写锁）。

---

### 8. `TransactionDeltaMerger<DI,NeedOutput,...>` — 增量合并器（`:21`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionDeltaMerger.hpp:21
template <
    class DI, bool NeedOutput, bool MutexProtected = true
    , class VersionDeltaMerger = TriviallyMerge<typename DI::Version, typename DI::VersionDelta>
    , class DataDeltaMerger    = TriviallyMerge<typename DI::Data, typename DI::DataDelta>
    , class KeyHashType        = std::hash<typename DI::Key>
>
class TransactionDeltaMerger {
public:
    // 接收 DI::Update，处理每个 OneFullUpdateItem 或 OneDeltaUpdateItem，
    // 更新 TransactionDataStore，并在 NeedOutput=true 时返回 DI::FullUpdate（变更键的快照）
    RetType operator()(typename DI::Update &&update) const;
};
```

`NeedOutput=true`：用于客户端侧，合并增量后输出变更键的全量快照（供 UI 刷新）。  
`NeedOutput=false`：用于服务端侧 `DataStoreUpdater`（作为纯 Exporter），只更新内存不产出。

---

### 9. `DefaultUtilities` — 默认策略实现（完整文件，`:9`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/DefaultUtilities.hpp

// 恒为常量的检查器（用于 VersionChecker / DataSummaryChecker）
template <class V, bool AlwaysAcceptInsert, bool AlwaysAcceptOther>
struct ConstChecker {
    bool operator()(V const &, V const &) const { return AlwaysAcceptOther; }
    // insert 场景使用 AlwaysAcceptInsert
};

// 用于 VersionDeltaMerger / DataDeltaMerger：直接赋值（忽略差量语义）
template <class Data, class DataDelta>
struct TriviallyMerge {
    void operator()(Data &d, DataDelta const &delta) const { d = delta; }
};

// 用于 DeltaProcessor：直接包装
template <class Data, class DataDelta, class ProcessedUpdate>
struct TriviallyProcess {
    ProcessedUpdate operator()(Data const &, DataDelta &&delta) const {
        return ProcessedUpdate{delta};
    }
};
```

---

### 10. `transactionLogicCombination` — 服务端组合入口（`:112`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/TransactionLogicCombination.hpp:112
template <class R, class TI, class DI, class DataStoreUpdater,
          SubscriptionLoggingLevel SLogging, TransactionLoggingLevel TLogging>
auto transactionLogicCombination(
    R &r
    , std::string const &componentPrefix
    , ITransactionFacility<typename R::AppType,TI,DI,TLogging,...> *transactionFacilityImpl
    , bool sealTransactionFacility = false
) -> TransactionLogicCombinationResult<R,TI,DI,...>;
```

返回结构（`:86`）：

```cpp
struct TransactionLogicCombinationResult {
    // OnOrderFacilityWithExternalEffects：处理事务请求，广播 DI::Update
    typename R::template OnOrderFacilityWithExternalEffectsPtr<
        typename TI::TransactionWithAccountInfo
        , typename TI::TransactionResponse
        , typename DI::Update
    > transactionFacility;

    // LocalOnOrderFacility：处理订阅请求，向每个订阅者推送 SubscriptionUpdate
    typename R::template LocalOnOrderFacilityPtr<
        typename GS::InputWithAccountInfo
        , typename GS::Output
        , typename GS::SubscriptionUpdate
    > subscriptionFacility;
};
```

内部连接关系：  
`transactionFacility` 的外部效果流（`DI::Update`）→ `subscriptionFacility` 的入站 + `DataStoreUpdater`（Exporter）双路广播。

`DataStoreUpdater` 模板参数需满足：
- `DataStoreUpdater::IsMutexProtected == R::AppType::PossiblyMultiThreaded`
- `DataStoreUpdater::DataStreamInterfaceType == DI`
- `DataStoreUpdater::KeyHash` 类型一致

通常用 `TransactionDeltaMerger<DI, false, MP>` 充当（`NeedOutput=false`，纯更新存储）。

---

### 11. `dataStreamClientCombination` — 客户端组合入口（`:92`）

```cpp
// tm_basic/tm_kit/basic/transaction/v2/DataStreamClientCombination.hpp:92
template <class R, class DI, class VersionDeltaMerger=..., class DataDeltaMerger=..., class KeyHashType=...>
auto dataStreamClientCombination(
    R &r
    , std::string const &componentPrefix
    , FacilitioidConnector<GS::Input, GS::Output> subscriptionFacility
    , Source<Key<GS::Input>> &&subscriptionKeySource
    , TransactionDataStorePtr<DI,...> *dataStorePtrOutput = nullptr
) -> DataStreamClientCombinationResult<R, DI>;
```

返回结构（`:77`）：

```cpp
struct DataStreamClientCombinationResult {
    Source<KeyedData<Input, DI::FullUpdate>> fullUpdates;          // 合并后的全量快照流
    Source<KeyedData<Input, GS::Output>> rawSubscriptionOutputs;   // 原始订阅响应（含 ack）
};
```

内部流程：将订阅响应中的 `SubscriptionUpdate`（`DI::Update`）提取出来，经 `TransactionDeltaMerger`（`NeedOutput=true`）合并成 `DI::FullUpdate`，输出给下游。

## 最小可用示例

### 服务端：定义 TI/DI，实现环境组件，调用 transactionLogicCombination

```cpp
// 来源：tm_examples/db_subscription/DBSubscriptionServer.cpp:31-47（已简化）
#include <tm_kit/basic/transaction/v2/TransactionLogicCombination.hpp>
using namespace dev::cd606::tm;

// 1. 定义 TI 与 DI（类型参数必须匹配）
using DI = basic::transaction::v2::DataStreamInterface<
    int64_t      // GlobalVersion
    , std::string  // Key（行名）
    , int64_t      // Version（行版本）
    , db_data      // Data
>;
using TI = basic::transaction::v2::TransactionInterface<
    int64_t, std::string, int64_t, db_data
>;
using GS = basic::transaction::v2::GeneralSubscriberTypes<boost::uuids::uuid, DI>;

// 2. 实现 DataStreamEnvComponent（初始化数据 + 后续变更通知）
// 来源：tm_examples/db_subscription/DBSubscriptionServer.cpp:49
class DSComponent : public basic::transaction::v2::DataStreamEnvComponent<DI> {
    Callback *cb_;
public:
    void initialize(Callback *cb) override {
        cb_ = cb;
        // 读取全量数据，发出初始全量 Update
        cb_->onUpdate(DI::Update {
            0, std::vector<DI::OneUpdateItem> { {DI::OneFullUpdateItem{...}} }
        });
    }
};

// 3. 实现 TransactionEnvComponent（事务逻辑 + 数据库写入）
// 来源：tm_examples/db_subscription/DBSubscriptionServer.cpp:88
class THComponent : public basic::transaction::v2::TransactionEnvComponent<TI> {
public:
    TI::GlobalVersion acquireLock(std::string const &, TI::Key const &, TI::DataDelta const *) override { ... }
    TI::GlobalVersion releaseLock(std::string const &, TI::Key const &, TI::DataDelta const *) override { ... }
    TI::TransactionResponse handleInsert(std::string const &acct, TI::Key const &k, TI::Data const &d) override { ... }
    TI::TransactionResponse handleUpdate(std::string const &acct, TI::Key const &k,
        std::optional<TI::VersionSlice> const &vs, TI::ProcessedUpdate const &pu) override { ... }
    TI::TransactionResponse handleDelete(std::string const &acct, TI::Key const &k,
        std::optional<TI::Version> const &v) override { ... }
};

// 4. 组合（M = RealTimeApp<Env>，Env 继承 DSComponent + THComponent）
using M = infra::RealTimeApp<TheEnv>;
using R = infra::AppRunner<M>;
R r(&env);

using DataStoreUpdater = basic::transaction::v2::TransactionDeltaMerger<
    DI, false, M::PossiblyMultiThreaded
>;

auto result = basic::transaction::v2::transactionLogicCombination<
    R, TI, DI, DataStoreUpdater
    , basic::transaction::v2::SubscriptionLoggingLevel::Verbose
    , basic::transaction::v2::TransactionLoggingLevel::Verbose
>(r, "db_server", new basic::transaction::v2::TransactionProcessor<M,TI,DI>());

// 5. 将两个 facility 注册并暴露给传输层（rabbitmq/multicast 等）
r.registerOnOrderFacilityWithExternalEffects("tx_facility", result.transactionFacility);
r.registerLocalOnOrderFacility("sub_facility", result.subscriptionFacility);
```

### 客户端：订阅变更并保持本地副本

```cpp
// 来源：tm_examples/db_subscription/DBSubscriptionClient.cpp:31-66（已简化）
#include <tm_kit/basic/transaction/v2/DataStreamClientCombination.hpp>
using DI = basic::transaction::v2::DataStreamInterface<int64_t, std::string, int64_t, db_data>;
using GS = basic::transaction::v2::GeneralSubscriberTypes<boost::uuids::uuid, DI>;
using M = infra::RealTimeApp<TheEnv>;
using R = infra::AppRunner<M>;
R r(&env);

// 建立到服务端 subscriptionFacility 的远程连接
auto facility = transport::MultiTransportRemoteFacilityManagingUtils<R>
    ::setupSimpleRemoteFacilityWithProtocol<basic::nlohmann_json_interop::Json, GS::Input, GS::Output>(
        r, "rabbitmq://127.0.0.1::guest:guest:test_db_cmd_subscription_queue"
    );

// 构造订阅请求 source
auto subKey = M::constFirstPushKeyImporter<GS::Input>(
    basic::VoidStruct{},
    GS::Input { GS::Subscription { std::vector<DI::Key> { targetKey } } }
);
r.registerImporter("sub_key", subKey);

// 组合客户端，获取合并后的全量更新流
auto clientResult = basic::transaction::v2::dataStreamClientCombination<R,DI>(
    r, "db_client"
    , r.facilityConnector(facility)
    , r.importerAsSource(subKey)
);

// clientResult.fullUpdates 是 Source<KeyedData<GS::Input, DI::FullUpdate>>
// 每次收到变更时获得变更键的最新全量快照
auto printAction = M::pureExporter<M::KeyedData<GS::Input, DI::FullUpdate>>(
    [](M::KeyedData<GS::Input, DI::FullUpdate> &&update) {
        for (auto const &item : update.data.data) {
            std::cout << "key=" << item.groupID
                      << " version=" << item.version << "\n";
        }
    }
);
r.exportItem(printAction, clientResult.fullUpdates);
```

## 实时 / 回测行为差异

| 维度 | 实时（`RealTimeApp`） | 回测（`SinglePassIterationApp`） |
|---|---|---|
| `DataStreamImporter` | `real_time::DataStreamImporter`，`start()` 调用 `DSComponent::initialize()`，后续变更通过 `onUpdate()` 异步注入 | `single_pass_iteration::DataStreamImporter`，缓存全部 Update 并通过 `generate()` 逐一输出 |
| 事务串行化 | TransactionProcessor 使用双缓冲队列 + 后台线程（`:101`） | 单线程执行，无队列，事务按到达顺序同步处理 |
| `TransactionDataStore::waitForGlobalVersion` | 忙等原子变量（`:33`），全局版本由后台线程提交后更新 | 单线程无竞争，版本立即可见 |
| `GeneralSubscriber` 锁 | 读写锁保护 subscriptionMap | 单线程无锁 |
| `DataStoreUpdater` mutex | `MutexProtected=true`，mutex 有效 | `MutexProtected=false`，mutex 为 `bool`（无开销） |
| `DataStreamImporterTypeResolver`（`:18`） | 解析为 `real_time::DataStreamImporter` | 解析为 `single_pass_iteration::DataStreamImporter` |

## 易错点

**1. TI 与 DI 的 GV/Key/Version/Data 必须完全相同类型**  
`TransactionProcessor`（`:70`）在特化约束中检查 `TI::GlobalVersion == DI::GlobalVersion` 等四个 `is_same_v`。类型不完全匹配时模板特化失败，报错在 `enable_if_t` 处，信息不直观。常见错误：TI 用 `int64_t` 版本而 DI 用 `uint64_t`，或 TI 的 `Data` 是 `MyStruct` 而 DI 的是 `proto::MyStruct`。

**2. DSComponent 的 `initialize` 必须发出至少一个全量 Update**  
`GeneralSubscriber` 在收到客户端 `SnapshotRequest` 时调用 `dataStore_->createFullUpdateNotification(keys)`。若 `initialize` 没有发出初始全量 Update，`dataMap_` 为空，所有 key 的快照均返回 `data = nullopt`（视为已删除），客户端会误以为数据不存在。

**3. `OneDeltaUpdateItem` 中的 key 必须已存在于 dataStore_**  
`TransactionDeltaMerger::handleDeltaUpdate`（`:54`）在 key 不存在或 `data` 为空时静默丢弃增量。若 full update 与 delta update 乱序到达（回测场景中可能发生），delta 会被无声丢弃。须保证 full update 先行到达。

**4. `TriviallyMerge` 将增量覆盖整个 Data，非真正增量合并**  
默认的 `TriviallyMerge<Data,DataDelta>` 实现是 `d = delta`，即直接用 delta 替换 data。若业务上 DataDelta 是真正的"差量"（只修改部分字段），必须提供自定义 `DataDeltaMerger`，否则会丢失未包含在 delta 中的字段。

**5. `transactionLogicCombination` 返回后 result 必须保持存活**  
`transactionFacility` 和 `subscriptionFacility` 是 `shared_ptr`，不能在 `AppRunner` 启动前被析构。通常将 result 声明在 `main` 或顶层函数作用域，避免局部变量提前析构。

**6. `dataStreamClientCombination` 中 subscriptionFacility 必须是 FacilitioidConnector**  
`dataStreamClientCombination` 的第三个参数类型是 `FacilitioidConnector<Input,Output>`，是可调用的"连接器"而非 `shared_ptr`。用 `r.facilityConnector(facility)` 从 `shared_ptr` 转换，而非直接传 `facility`。

**7. `GeneralSubscriberTypes::Input` 的 variant 须用 `SingleLayerWrapper` 包裹**  
创建订阅请求时需要 `GS::Input { GS::Subscription{...} }`，其中 `GS::Input` 是 `SingleLayerWrapper<variant<...>>`，而非 `variant` 本身。遗漏 `SingleLayerWrapper` 包装会导致类型不匹配编译错误。

## 第三方依赖

`transaction::v2` 头文件本身无直接第三方依赖，仅使用标准库（`<unordered_map>`、`<mutex>`、`<atomic>`、`<thread>`）。

外部依赖出现在使用层：

- **SOCI** — 示例中 `DSComponent`/`THComponent` 使用 SOCI 访问 SQLite3/MySQL（`soci/soci.h`，`:22`）。SOCI 文档：https://soci.sourceforge.net/doc/master/；vcpkg 包名：`soci`（参见 `CLAUDE.md` 中的 `.pc` 修补说明）。
- **Boost.UUID** — 服务端订阅 ID 类型常用 `boost::uuids::uuid`，通过 `BoostUUIDComponent` 生成。官方文档：https://www.boost.org/doc/libs/release/libs/uuid/

## 相关章节

- [共享链](08-shared-chain.md) — 与 transaction v2 并列的另一种状态存储模式；`simple_shared_chain` 更适合单写入点的 append-only 日志，transaction v2 更适合多客户端并发修改的键值表
- [序列化格式](03-serialization.md) — `TI::Transaction`、`GS::Input`/`Output` 均通过 `RunSerializer<Proto<T>>` 或 `RunSerializer<Json<T>>` 在 transport 层编解码
- [AppRunner 与节点连接](../tm_infra/05-app-runner.md) — `transactionLogicCombination` 返回的 facility 通过 `AppRunner` 注册并与 transport 层连接
- [tm_transport 传输工具](../tm_transport/02-facilities.md) — `MultiTransportFacilityWrapper` / `MultiTransportRemoteFacilityManagingUtils` 将 transactionFacility 暴露为网络服务
- [CommonFlowUtils](05-common-flow-util.md) — `dataStreamClientCombination` 内部使用 `CommonFlowUtilComponents::withKeyAndInput` 包装 kleisli 合并逻辑
