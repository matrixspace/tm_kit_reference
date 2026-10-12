---
title: 共享链（simple_shared_chain）
library: tm_basic
headers: [tm_kit/basic/simple_shared_chain/ChainReader.hpp, tm_kit/basic/simple_shared_chain/ChainWriter.hpp, tm_kit/basic/simple_shared_chain/OneShotChainWriter.hpp, tm_kit/basic/simple_shared_chain/ChainPollingPolicy.hpp, tm_kit/basic/simple_shared_chain/InMemoryLockFreeChain.hpp, tm_kit/basic/simple_shared_chain/InMemoryWithLockChain.hpp, tm_kit/basic/simple_shared_chain/InMemorySharedChainCreator.hpp, tm_kit/basic/simple_shared_chain/ChainDataImporterExporter.hpp, tm_kit/basic/simple_shared_chain/SelfContainedChainModifier.hpp, tm_kit/basic/simple_shared_chain/ChainBackedFacility.hpp, tm_kit/basic/simple_shared_chain/FolderUsingPartialHistoryInformation.hpp]
keywords: [simple_shared_chain, ChainReader, ChainWriter, OneShotChainWriter, ChainPollingPolicy, ChainItemFolder, FolderUsingPartialHistoryInformation, ChainWritingStatus, InMemoryLockFreeChain, InMemoryWithLockChain, InMemorySharedChainCreator, ChainDataImporterExporter, SelfContainedChainModifier, ChainBackedFacility, BasicWithTimeAppChainCreator, 事件溯源, 共享链, 链读取, 链写入, 单次写入]
---

# 共享链（simple_shared_chain）

## 用途

`simple_shared_chain` 是 TM Kit 中的**事件溯源**抽象层——将有序的事件序列存储在一条单向链上，任意数量的读取者均可从头（或中间某个检查点）开始折叠链上所有事件，任意数量的写入者通过 CAS（Compare-And-Swap）或 mutex 竞争追加新节点。

主要组件：

- **Chain 协议**（`ChainReader.hpp` / `ChainWriter.hpp`）— 链的最小接口要求，不限制底层存储
- **`ChainPollingPolicy`** — 读取轮询参数（睡眠时长、忙等模式等）
- **`ChainItemFolder`** — 折叠器协议；将链上的每个事件折叠到状态 `ResultType` 中
- **`ChainReader<App,Chain,Folder,TriggerT,ResultTransformer>`** — 生产框架节点（Importer 或 Action）
- **`ChainWriter<App,Chain,Folder,InputHandler,IdleLogic>`** — 生产框架节点（OnOrderFacility 或带 ExternalEffects 的变体）
- **`OneShotChainWriter`** — 不依赖框架的一次性写入工具
- **`InMemoryLockFreeChain<T>`** / **`InMemoryWithLockChain<T>`** — 两种进程内实现
- **`InMemorySharedChainCreator<App>`** — 统一工厂，按描述符字符串创建链与框架节点

## 头文件与命名空间

```cpp
// 各组件有独立头文件；常见用法通过 Creator 一次引入大部分内容
#include <tm_kit/basic/simple_shared_chain/InMemorySharedChainCreator.hpp>
// 或按需单独引入
#include <tm_kit/basic/simple_shared_chain/ChainReader.hpp>
#include <tm_kit/basic/simple_shared_chain/ChainWriter.hpp>
#include <tm_kit/basic/simple_shared_chain/OneShotChainWriter.hpp>

namespace dev::cd606::tm::basic::simple_shared_chain
```

## 核心类型与签名

### 1. Chain 协议（所有链实现须满足）

任何链类型必须提供以下静态/实例成员（由 `ChainReader` / `ChainWriter` 通过 Boost.Hana 检测）：

```cpp
// 类型成员
using StorageIDType = std::string;      // 节点 ID 类型（通常为 string）
using DataType      = T;                // 节点携带的业务数据类型
using ItemType      = /* 节点类型 */;   // 包含 id + data + nextID
static constexpr bool SupportsExtraData = true/false; // 是否支持 saveExtraData/loadExtraData

// 链遍历
std::optional<ItemType> fetchNext(ItemType const &current);  // 返回 nullopt 表示链尾
bool appendAfter(ItemType const &current, ItemType &&toBeWritten); // CAS/mutex；ID 重复则返回 false
bool appendAfter(ItemType const &current, std::vector<ItemType> &&batch); // 批量追加

// 定位
ItemType head(void *env);                                    // 返回虚拟头节点（id=""）
ItemType loadUntil(void *env, StorageIDType const &id);      // 跳到指定节点（回放优化）

// 静态工具
static ItemType formChainItem(StorageIDType id, DataType &&data);
static std::vector<ItemType> formChainItems(std::vector<std::tuple<StorageIDType, DataType>> &&);
template <class Env> static StorageIDType newStorageID();   // 生成新 UUID 字符串
template <class Env> static std::string newStorageIDAsString();
static DataType const *extractData(ItemType const &);       // 空节点返回 nullptr
static std::string_view extractStorageIDStringView(ItemType const &);

// 可选：带数据锁的链（ChainLock<Chain> 会检测并调用）
void acquireLock();
void releaseLock();
static constexpr bool DataLockIsTrivial = false; // true 则 ChainLock 不调用 acquire/release

// 可选：阻塞等待新数据（ChainReader 在轮询无数据时调用）
void waitForUpdate(std::chrono::system_clock::duration duration);

// 可选：链外附加数据（当 SupportsExtraData == true）
template <class ExtraData> void saveExtraData(std::string const &key, ExtraData const &data);
template <class ExtraData> std::optional<ExtraData> loadExtraData(std::string const &key);
```

---

### 2. `ChainPollingPolicy`（`ChainPollingPolicy.hpp:7`）

```cpp
struct ChainPollingPolicy {
    bool callbackPerUpdate = false;    // true：每个新节点触发一次输出（而非每次轮询）
    bool busyLoop = false;             // true：不睡眠，持续轮询
    bool noYield = false;              // true：不调用 std::this_thread::yield()
    std::chrono::system_clock::duration readerPollingWaitDuration
        = std::chrono::milliseconds(1);

    // 链式构建器
    static ChainPollingPolicy CallbackPerUpdate();
    static ChainPollingPolicy BusyLoop();
    static ChainPollingPolicy NoYield();
    static ChainPollingPolicy ReaderPollingWaitDuration(std::chrono::system_clock::duration d);
};
```

---

### 3. `ChainItemFolder` 协议

折叠器不继承任何基类，`ChainReader` / `ChainWriter` 用 Boost.Hana 检测其成员：

```cpp
class MyFolder {
public:
    using ResultType = MyState; // 必须：折叠结果类型

    // 必须：初始化（在链头之前调用）
    MyState initialize(Env *env, Chain *chain);

    // 必须二选一：
    MyState fold(MyState const &state, std::string_view id, DataType const &data);
    // 或（原地版，避免拷贝）：
    void foldInPlace(MyState &state, std::string_view id, DataType const &data);

    // 可选：跳过不感兴趣的节点（返回 false 则不调用 fold/foldInPlace）
    bool filterUpdate(std::string_view id, DataType const &data);

    // 可选：当继承 FolderUsingPartialHistoryInformation 时提供；
    // 返回非空值时 ChainReader 从该 ID 开始而非从链头重放
    std::string chainIDForState(MyState const &state);
};
```

`FolderUsingPartialHistoryInformation`（`FolderUsingPartialHistoryInformation.hpp:5`）是空标记结构体，折叠器继承它以声明自己支持部分历史跳过。

#### 3.1 框架自带的 ChainItemFolder 实现（`ChainReader.hpp:762`–`:900`）

多数场景不需要自己写折叠器——`ChainReader.hpp` 提供了一组现成的：

| 类型 | 行号 | `ResultType` | 语义 |
|---|---|---|---|
| `TrivialChainDataFetchingFolder<ChainDataType>` | `:775` | `std::optional<ChainDataType>` | **最常用**。只保留链上最新一条数据，忽略 id |
| `TrivialChainIDAndDataFetchingFolder<ChainDataType>` | `:762` | `std::optional<tuple<string, ChainDataType>>` | 同上，但同时保留该条目的 id |
| `TrivialChainDataFetchingFolderWithTime<ChainDataType, Env>` | `:786` | `std::optional<ChainDataType>` | 在 `TrivialChainDataFetchingFolder` 基础上**多了 `extractTime(ResultType const&)`**，用构造时传入的提取器算出该条目对应的时间戳——回测重放时用它给数据打时间 |
| `EmptyStateChainFolder` | `:803` | `VoidStruct` | 不折叠任何状态；只关心"链上有新条目"这件事本身 |

前三个都继承 `FolderUsingPartialHistoryInformation`。

`TrivialChainDataFetchingFolderWithTime` 是**回测场景的关键**：`SharedChainCreator::reader` 需要知道每条数据的时间才能驱动单遍迭代时钟，而链上只存了数据、没存时间。构造时传入的 `timeExtractor` 就是"从数据算出时间"的函数：

```cpp
// 来源：tm_basic/tm_kit/basic/simple_shared_chain/ChainReader.hpp:788-791（签名）
TrivialChainDataFetchingFolderWithTime(
    std::function<typename Env::TimePointType(std::optional<ChainDataType> const &)> const &timeExtractor
);
```

`SaveDataOnChain<Chain, T>`（`:30`）不是折叠器，是个**追加辅助**：`operator()(key, data)` 调 `chain->saveExtraData<T>(key, data)`（当 `Chain::SupportsExtraData` 时）。用于把"链外"的辅助数据也挂到链上，供后续读取。

#### 3.2 `CombinedFolder`：合并多个折叠器

```cpp
// ChainReader.hpp:822 — 主模板为空（仅在 bool 非类型参数下特化）
template <class FolderA, class FolderB, bool usesPartialHistory = /* A 或 B 是 PartialHistory */>
class CombinedFolder;

// :824 — 不涉及部分历史
template <class FolderA, class FolderB>
class CombinedFolder<FolderA, FolderB, false> {
public:
    using ResultType = std::tuple<typename FolderA::ResultType, typename FolderB::ResultType>;
    CombinedFolder(FolderA &&folderA, FolderB &&folderB);
};

// :868 — 涉及部分历史（额外继承 FolderUsingPartialHistoryInformation）
template <class FolderA, class FolderB>
class CombinedFolder<FolderA, FolderB, true> : public FolderUsingPartialHistoryInformation, ...;
```

第三个模板参数有默认值：只要 A 或 B 中任一个是 `FolderUsingPartialHistoryInformation` 的子类，就自动选到支持部分历史的特化（`:816`–`:820` 的 `std::is_convertible_v` 判断）。因此**通常不需要显式写第三个参数**。

`ResultType` 是 `tuple<A::ResultType, B::ResultType>`——两个折叠器各自维护状态，最终结果打包在一起返回。

---

### 4. `ChainReader`（`ChainReader.hpp:48`）

```cpp
// TriggerT=void → 生产 Importer；TriggerT=非void → 生产 Action
template <class App, class Chain, class ChainItemFolder,
          class TriggerT=VoidStruct, class ResultTransformer=void>
class ChainReader {
public:
    // 当 TriggerT=void：创建 Importer，持续轮询链并发布折叠结果
    static std::shared_ptr<typename App::template Importer<OutputType>>
    importer(Chain *chain,
             ChainPollingPolicy const &pollingPolicy = {},
             ChainItemFolder &&folder = {},
             ResultTransformerOrBool &&resultTransformer = {});

    // 当 TriggerT=非void：创建 Action，每次收到触发信号时折叠到链尾并返回结果
    static std::shared_ptr<typename App::template Action<TriggerT, OutputType>>
    action(typename App::EnvironmentType *env,
           Chain *chain,
           ChainItemFolder &&folder = {},
           ResultTransformerOrBool &&resultTransformer = {});
};
// OutputType = ResultTransformer==void ? ChainItemFolder::ResultType
//                                      : ResultTypeExtractor<ResultTransformer>::TheType
```

`ResultTransformer` 若非 `void`，须为 `ResultType → OutputType` 的可调用对象（或带 `ResultType` 成员的类）。

---

### 5. `ChainWritingStatus`（`ChainWriter.hpp:72`）与 `InputHandler` 协议

```cpp
enum class ChainWritingStatus {
    NoWritingRequired,   // handleInput 决定本次无需写入
    SuccessfullyWritten, // appendAfter 成功
    FailedToWrite        // appendAfter 失败（被其他写入者抢先）
};
```

`InputHandler` 协议（无需继承基类，Hana 检测）：

```cpp
class MyInputHandler {
public:
    using InputType    = /* 请求类型 */;
    using ResponseType = /* 响应类型 */;

    // 可选初始化
    static void initialize(Env *env, Chain *chain);

    // 核心：处理一次请求；返回 (response, 要写入的条目)
    // 单条写入：
    auto handleInput(Env *env, Chain *chain,
                     InnerData<Key<InputType,Env>> const &input,
                     StateType const &currentState)
        -> std::tuple<ResponseType, std::optional<std::tuple<std::string, Chain::DataType>>>;
    // 批量写入（多条）：
    auto handleInput(...)
        -> std::tuple<ResponseType, std::vector<std::tuple<std::string, Chain::DataType>>>;
    // id 字符串若为空，ChainWriter 自动生成 UUID
};
```

---

### 6. `ChainWriter`（`ChainWriter.hpp:22`）

```cpp
template <class App, class Chain, class ChainItemFolder,
          class InputHandler, class IdleLogic=void>
class ChainWriter {
public:
    // IdleLogic=void：普通 OnOrderFacility
    static std::shared_ptr<typename App::template OnOrderFacility<
        InputType, std::tuple<ChainWritingStatus, ResponseType>>>
    onOrderFacility(Chain *chain,
                    ChainPollingPolicy const &pollingPolicy = {},
                    ChainItemFolder &&folder = {},
                    InputHandler &&inputHandler = {});

    // IdleLogic≠void：OnOrderFacilityWithExternalEffects（后台线程运行 IdleLogic）
    static std::shared_ptr<typename App::template OnOrderFacilityWithExternalEffects<
        InputType, std::tuple<ChainWritingStatus, ResponseType>,
        IdleLogic::OffChainUpdateType>>
    onOrderFacilityWithExternalEffects(...);
};
```

`IdleLogic` 协议：
- `using OffChainUpdateType = ...;`
- `work(env, chain, currentState) -> tuple<optional<OffChainUpdateType>, optional<tuple<string, DataType>>>`

`ChainLock<Chain>`（`ChainWriter.hpp:34`）是 RAII helper，在 `appendAfter` 调用周期内持有链的 `acquireLock/releaseLock`（当链提供该接口时）。

#### 6.1 框架自带的 InputHandler / IdleLogic 实现（`ChainWriter.hpp:1983`–`:2100`）

不必从零写协议——`ChainWriter.hpp` 末尾提供了一组开箱即用的实现，覆盖最常见的写入语义：

| 类型 | 行号 | 语义 |
|---|---|---|
| `SimplyPlaceOnChainInputHandler<Env,ChainData>` | `:2020` | **最常用**。收到请求就无条件写入一条 `ChainData`，响应 `bool`。`InputType = ChainData`、`ResponseType = bool` |
| `SimplyPlaceMultipleOnChainInputHandler<Env,ChainData>` | `:2055` | 一次请求写入多条（`InputType` 是 `vector<ChainData>` 之类），用于批量提交 |
| `SimplyTryPlaceOnChainOnceInputHandler<Env,ChainData>` | `:2033` | 只在**链上尚不存在**该条目时写入一次；用于幂等初始化。构造时需传入用于判重的提取器 |
| `CompletelyEmptyInputHandler` | `:2007` | 什么都不做、不写链；用于只需要 `IdleLogic` 产出外部数据的场景 |
| `EmptyInputHandler` | `:1994` | 更空的占位实现 |
| `EmptyIdleWorker` | `:1983` | `IdleLogic` 的空实现（配合 `IdleLogic≠void` 的形态，占用位但不产出外部数据） |
| `SimplyReturnStateIdleLogic` | `:2077` | `IdleLogic` 实现：直接返回当前折叠状态作为外部更新 |

`SimplyPlaceOnChainInputHandler` 的实现极简，可当作写自定义 handler 的模板（`:2020`）：

```cpp
// 来源：tm_basic/tm_kit/basic/simple_shared_chain/ChainWriter.hpp:2020-2031
template <class Env, class ChainData>
class SimplyPlaceOnChainInputHandler {
public:
    using InputType = ChainData;
    using ResponseType = bool;
    static void initialize(void *, void *) {}
    template <class ChainState>
    static std::tuple<ResponseType, std::optional<std::tuple<std::string, ChainData>>>
    handleInput(Env *, void *, typename infra::RealTimeApp<Env>::template TimedDataType<
            typename infra::RealTimeApp<Env>::template Key<ChainData>> const &input, ChainState const &) {
        return {true, {{"", input.value.key()}}};   // id 留空 → ChainWriter 自动生成 UUID
    }
};
```

注意 `initialize` 与 `handleInput` 的第二、三个参数是 `void *` 而非 `Env *` / `Chain *`——协议对参数类型是宽松的，写自定义 handler 时用具体类型也可以（Hana 检测只看方法名与参数个数）。

`ChainWritingResult`（`ChainWriter.hpp:78`）是 `std::tuple<ChainWritingStatus, ResponseType>` 的别名，即 `ChainWriter` 产出的 facility 的响应类型。

工厂封装：`ChainWriterOnOrderFacilityFactory`（`:2097`）与 `ChainWriterOnOrderFacilityWithExternalEffectsFactory`（`:2092`）是 `std::function` 别名（不是类），把上述两个静态函数包成可传递的工厂对象。

**`SingleWritingMode` 优化开关**：自定义 `InputHandler` 可以声明 `static constexpr bool SingleWritingMode = true;` 来告诉框架"我永远只写一条"。`Has_SingleWritingMode<T>` trait（`:81`、`:84`）用 SFINAE 检测这个成员，未声明时默认 `false`（走通用路径）。声明它的 handler 能省掉一次 vector 构造与遍历。

---

### 7. `OneShotChainWriter`（`OneShotChainWriter.hpp:13`）

不依赖框架，可在任意上下文调用（初始化、测试、命令行工具）：

```cpp
template <class Env, class Chain>
class OneShotChainWriter {
public:
    // 使用折叠器得到当前状态，再调用 f 决定写什么
    // f: ResultType -> optional<tuple<string, DataType>>  （单条）
    // f: ResultType -> vector<tuple<string, DataType>>    （多条，:70）
    template <class ChainItemFolder, class F>
    static bool write(Env *env, Chain *chain, F &&f,
                      ChainItemFolder &&folder = {});

    // 无需折叠，直接写一个已知值（单次尝试）
    static bool tryWriteConstValue(
        Env *env, Chain *chain,
        std::string const &storageID,
        typename Chain::DataType &&value);  // :88

    // 无需折叠，阻塞直到写入成功（循环重试）
    static void blockingWriteConstValue(
        Env *env, Chain *chain,
        std::string const &storageID,
        typename Chain::DataType &&value);  // :103
};
```

`write` 在 CAS 失败（`appendAfter` 返回 false）时重新折叠并重试，直到成功或 `f` 返回 nullopt/空 vector。

---

### 8. 内存链实现

#### `InMemoryLockFreeChain<T>`（`InMemoryLockFreeChain.hpp:31`）

基于原子指针的无锁链表：
- `SupportsExtraData = true`，链外数据存于 `std::atomic<...>` 保护的字典
- `appendAfter` 用原子 CAS；并发写入时失败率随竞争程度增加
- 无 `waitForUpdate` ——读取器只能轮询或睡眠

#### `InMemoryWithLockChain<T>`（`InMemoryWithLockChain.hpp:30`）

基于 `std::mutex` 的有锁链，所有写入/读取均加锁：

```cpp
template <class T>
class InMemoryWithLockChain {
public:
    // 注册更新触发回调（仅调用一次；appendAfter 后自动调用）
    void setUpdateTriggerFunc(std::function<void()> f);  // :49
    // 内部 condition_variable：appendAfter 后 notify_all（:104）
};
// 带 CBOR 序列化的内部节点类型：
// InMemoryWithLockChainItem<T>  — fields: revision, id, data, nextID  (:20)
// InMemoryWithLockChainStorage<T> — fields: data, nextID              (:21)
```

---

### 9. `InMemorySharedChainCreator<App>`（`InMemorySharedChainCreator.hpp:19`）

统一工厂，以描述符字符串区分链类型（单例，同一描述符返回同一链实例）：

| 描述符前缀 | 链类型 |
|---|---|
| `"empty://..."` | `EmptyChain`（所有操作无效，用于 BasicWithTimeApp 测试） |
| `"lock_free://..."` | `InMemoryLockFreeChain<ChainData>` |
| 其他 | `InMemoryWithLockChain<ChainData>` |

```cpp
template <class App>
class InMemorySharedChainCreator {
public:
    // 创建读取器工厂（TriggerT=void→Importer，否则→Action）
    template <class ChainData, class ChainItemFolder,
              class TriggerT=void, class ResultTransformer=void>
    auto readerFactory(
        typename App::EnvironmentType *env,
        std::string const &descriptor,
        ChainPollingPolicy const &pollingPolicy = {},
        ChainItemFolder &&folder = {},
        /* resultTransformer */ ...
    ) -> /* ImporterFactory 或 ActionFactory */;

    // 创建写入器工厂（IdleLogic=void→OnOrderFacility，否则→WithExternalEffects）
    template <class ChainData, class ChainItemFolder,
              class InputHandler, class IdleLogic=void>
    auto writerFactory(
        typename App::EnvironmentType *env,
        std::string const &descriptor,
        ChainPollingPolicy const &pollingPolicy = {},
        ChainItemFolder &&folder = {},
        InputHandler &&inputHandler = {},
        /* idleLogic */ ...
    ) -> /* FacilityFactory 或 FacilityWithExternalEffectsFactory */;

    // 链外数据直接读写
    template <class ChainData, class ExtraData>
    static void writeExtraData(typename App::EnvironmentType *env,
        std::string const &descriptor, std::string const &key, ExtraData const &data);
    template <class ChainData, class ExtraData>
    static std::optional<ExtraData> readExtraData(typename App::EnvironmentType *env,
        std::string const &descriptor, std::string const &key);
};
```

工厂方法返回的工厂对象（callable `() -> shared_ptr<Node>`）可直接传给 `createChainDataSource` / `createChainDataSink`。

---

### 10. `ChainDataImporterExporter`（`ChainDataImporterExporter.hpp`）

高层辅助函数，将链读写器直接注册进 `AppRunner`：

```cpp
// 注册链 importer，返回 Source<ChainData>（:14）
template <class R, class ChainData>
typename R::template Source<ChainData>
createChainDataSource(R &r,
    /* readerFactory（ChainReader::importer 的返回值） */ chainReaderFactory,
    std::string const &prefix);

// 注册链写入 facility，返回 Sink<ChainData>（:41）
// ⚠️ 仅用于无条件写入（不需要读当前状态）
template <class R, class ChainData>
typename R::template Sink<ChainData>
createChainDataSink(R &r,
    /* writerFactory */ chainWriterFactory,
    std::string const &prefix);

// 将输入链数据转录到输出链（:71）
template <class R, template <class M> class ChainCreator, class ChainData>
typename R::template Source<ChainData>
setupChainTranscriber(R &r,
    ChainCreator<typename R::AppType> &chainCreator,
    std::string const &inputChainDescriptor,
    std::string const &outputChainDescriptor,
    std::function<typename R::AppType::TimePoint(ChainData const &)> const &timestampExtractor,
    std::string const &prefix);
```

---

### 11. `SelfContainedChainModifier`（`SelfContainedChainModifier.hpp:29`）

将"读取链状态 → 计算 → 写回"整合为一个自驱节点：

```cpp
template <class R, template <class M> class ChainCreator,
          class ChainData, class ChainItemFolder, class IdleLogic>
void createSelfContainedChainModifier(
    R &r,
    ChainCreator<typename R::AppType> &chainCreator,
    std::string const &chainDescriptor,
    std::string const &prefix,
    std::optional<typename R::template Source<VoidStruct>> drivingUpdate = std::nullopt,
    ChainPollingPolicy const &pollingPolicy = {},
    ChainItemFolder &&chainItemFolder = {},
    IdleLogic &&idleLogic = {}
);
```

- `drivingUpdate` 有值时：注册为 OnOrderFacility，由外部 `VoidStruct` 信号驱动
- `drivingUpdate` 无值时：注册为 OnOrderFacilityWithExternalEffects，由 IdleLogic 自驱

---

### 12. `ChainBackedFacility`（`ChainBackedFacility.hpp:18`）

将链状态更新路由回等待中的 facility 请求：

```cpp
// IDAndFinalFlagExtractor 协议：
// extract(ChainData const &) -> vector<tuple<ID, bool>>  （是否为最终响应）
// writeSucceeded(ResponseType const &) -> bool

template <class R, class ChainData, class ChainItemFolder,
          class InputHandler, class IDAndFinalFlagExtractor, class IdleLogic=void>
struct ChainBackedFacilityOutput {
    typename R::template FacilitioidConnector<
        InputHandler::InputType, optional<ChainData>> facility;
    typename R::template Sourceoid<
        OffChainUpdateTypeExtractor<IdleLogic>::T> offChainUpdateSource;
    std::string registeredNameForFacilitioidConnector;
};
```

## 最小可用示例

### InMemorySharedChainCreator：事件溯源订单簿（实时模式）

```cpp
// 来源：tm_examples/simple_demo 链写入模式（已简化）
#include <tm_kit/basic/simple_shared_chain/InMemorySharedChainCreator.hpp>
using M = infra::RealTimeApp<TheEnvironment>;
using App = M;

// 业务数据类型（必须有 StructFieldInfo，即 TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE）
TM_BASIC_CBOR_CAPABLE_STRUCT(OrderEvent,
    ((std::string, orderId))
    ((double, price))
    ((int32_t, qty))
);
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES(OrderEvent,
    ((std::string, orderId))((double, price))((int32_t, qty))
);

// 折叠器：维护所有活跃订单的映射
struct OrderBookFolder {
    using ResultType = std::unordered_map<std::string, double>;
    ResultType initialize(TheEnvironment *, auto *) { return {}; }
    void foldInPlace(ResultType &state, std::string_view, OrderEvent const &ev) {
        if (ev.qty == 0) state.erase(ev.orderId);
        else state[ev.orderId] = ev.price;
    }
};

// InputHandler：接受新事件，写入链
struct OrderInputHandler {
    using InputType    = OrderEvent;
    using ResponseType = bool;
    auto handleInput(TheEnvironment *env, auto *chain,
                     auto const &input, auto const &state)
        -> std::tuple<bool, std::optional<std::tuple<std::string, OrderEvent>>> {
        // 使用 "" 让 ChainWriter 自动生成 UUID
        return { true, std::make_tuple("", input.timedData.value.key()) };
    }
};

// 使用 InMemorySharedChainCreator
InMemorySharedChainCreator<App> chainCreator;
std::string desc = "lock_free://orderbook";

// 1. 创建写入 facility 并注册
auto writerFact = chainCreator.template writerFactory<
    OrderEvent, OrderBookFolder, OrderInputHandler
>(r.environment(), desc);
auto writer = writerFact();
r.registerOnOrderFacility("orderbook/writer", writer);

// 2. 创建读取 importer 并注册
auto readerFact = chainCreator.template readerFactory<
    OrderEvent, OrderBookFolder
>(r.environment(), desc, simple_shared_chain::ChainPollingPolicy{});
auto source = createChainDataSource<decltype(r), OrderEvent>(r, readerFact, "orderbook/reader");
```

### OneShotChainWriter：进程启动时写入初始状态

```cpp
// 来源：tm_examples/simple_demo 初始化模式（已简化）
#include <tm_kit/basic/simple_shared_chain/OneShotChainWriter.hpp>
#include <tm_kit/basic/simple_shared_chain/InMemoryWithLockChain.hpp>
using namespace dev::cd606::tm::basic::simple_shared_chain;

InMemoryWithLockChain<OrderEvent> chain;
TheEnvironment env;

// 阻塞写入初始事件（直到成功）
OneShotChainWriter<TheEnvironment, InMemoryWithLockChain<OrderEvent>>::blockingWriteConstValue(
    &env, &chain, "",  // "" → 自动生成 UUID
    OrderEvent {"INIT", 0.0, 0}
);

// 基于当前状态写入（先折叠再决定写什么）
OneShotChainWriter<TheEnvironment, InMemoryWithLockChain<OrderEvent>>::write(
    &env, &chain,
    [](OrderBookFolder::ResultType const &state) 
        -> std::optional<std::tuple<std::string, OrderEvent>> {
        if (state.empty()) {
            return { {"", OrderEvent{"SEED", 100.0, 10}} };
        }
        return std::nullopt;  // 已有数据，无需写入
    },
    OrderBookFolder{}
);
```

## 实时 / 回测行为差异

| 维度 | 实时（`RealTimeApp`） | 回测（`SinglePass`/`TopDown`） |
|---|---|---|
| ChainReader importer | 后台线程持续轮询；有 `waitForUpdate` 时等待通知 | 单线程同步折叠；轮询等待无意义，直接继续 |
| ChainWriter | 后台线程持续检查新请求，CAS/mutex 写入 | 同步处理请求，无后台线程 |
| `InMemoryLockFreeChain` | 线程安全；并发写入 CAS 竞争 | 无并发竞争，CAS 必成功 |
| `InMemoryWithLockChain` | mutex + condition_variable 配合等待新数据 | mutex 保护仍有效，但 wait 语义无意义 |
| `BasicWithTimeAppChainCreator` | 所有操作为 no-op | 所有操作为 no-op（纯测试用） |
| 轮询等待时长 | `readerPollingWaitDuration` 实际睡眠 | 框架忽略睡眠，直接处理下一事件 |

## 易错点

**1. 链数据类型必须有 `StructFieldInfo` 反射（CBOR 序列化宏）**  
`InMemorySharedChainCreator` 在链外数据（`saveExtraData`/`loadExtraData`）中使用 `RunSerializer<CBOR<ExtraData>>`，要求 `ExtraData` 有 CBOR 序列化支持。链上的 `DataType` 本身不强制要求序列化（进程内链不需要序列化），但跨进程持久化链（如 etcd/Redis 链，见 tm_transport）的 `DataType` 必须可序列化。

**2. `createChainDataSink` 仅适用于无条件写入**  
`ChainDataImporterExporter.hpp:41` 的注释明确警告：`createChainDataSink` 生成的节点不读取当前链状态就直接写入，因此只适合"无论链上有什么都追加"的场景（如日志流）。若写入内容依赖当前状态（如更新订单簿），必须使用 `ChainWriter::onOrderFacility` 并自定义 `InputHandler`。

**3. `appendAfter` 返回 `false` 是正常的竞态失败，不是错误**  
多写入者并发时，`appendAfter` 在第一个写入者胜出后对其余写入者返回 false。`ChainWriter` 会重新折叠并重试，`OneShotChainWriter::write` 也会重试。如果自定义代码直接调用 `appendAfter` 而不循环重试，会静默丢失写入。

**4. `ChainItemFolder::chainIDForState` 需要继承 `FolderUsingPartialHistoryInformation`**  
若折叠器实现了 `chainIDForState` 方法但没有继承 `FolderUsingPartialHistoryInformation`，`ChainReader` 的编译期检测（`:216–219`）不会触发跳过重放的逻辑——仍然从链头开始，`chainIDForState` 被忽略。二者缺一不可。

**5. `InMemorySharedChainCreator` 按描述符字符串做单例，描述符拼写必须完全一致**  
同一进程内，描述符 `"lock_free://orders"` 和 `"lock_free://Orders"` 是两条不同的链。读取器和写入器的描述符必须字节完全相同，否则读取不到写入方的数据。

**6. `SelfContainedChainModifier` 无 `drivingUpdate` 时依赖 IdleLogic 自驱，需将 facility 连接好**  
当 `drivingUpdate` 为 `std::nullopt` 时，注册的是 `OnOrderFacilityWithExternalEffects`；框架要求该节点的外部效果输出必须连接到某个 exporter，否则图检查（GraphCheck）会报告悬空连接。代码中（`:76–88`）创建了 `discard2` exporter，但若忘记连接 `facilityWithExternalEffectsAsSource`，图会不完整。

**7. `ChainWriter` 在 RealTimeApp 下的折叠是在请求到达时同步进行的**  
每次 facility 收到请求，`ChainWriter` 先把链上所有未处理的新节点折叠进状态（`:266–284`），再调用 `InputHandler::handleInput`，再尝试 `appendAfter`。若链上积累了大量节点，这一折叠步骤会在调用方的等待时间内完成，可能造成延迟抖动。高吞吐场景应考虑在折叠器中使用 `foldInPlace`（避免拷贝）或基于 `FolderUsingPartialHistoryInformation` 的检查点机制。

## 第三方依赖

- **Boost.Hana** — `ChainReader.hpp:14`、`ChainWriter.hpp:19`，用于编译期检测 `foldInPlace`、`filterUpdate`、`waitForUpdate`、`chainIDForState` 等可选方法是否存在（`boost::hana::is_valid`）。
- **Boost（线程库）** — `InMemoryWithLockChain` 和 `ChainWriter` 使用标准库 `std::mutex`、`std::condition_variable`、`std::thread`，无额外 Boost 线程依赖。
- **跨进程/持久化链**（在 tm_transport 中，不在本模块）— etcd 链、Redis 链、RocksDB 链各自依赖对应的第三方库（见 `tm_transport/04-shared-chains.md`）。

## 相关章节

- [AppRunner 与图构建](../tm_infra/05-app-runner.md) — `registerOnOrderFacility`、`registerImporter`、`placeOrderWithFacility` 等连接 API
- [on-order facility 四种变体](../tm_infra/04-facilities.md) — `OnOrderFacility`、`OnOrderFacilityWithExternalEffects`、VIE facility 的连接语义
- [序列化格式](03-serialization.md) — 跨进程持久化链的 `DataType` 需经 `RunSerializer`/`RunDeserializer` 编解码
- [CommonFlowUtils](05-common-flow-util.md) — `wholeHistoryFold` 可配合链读取做全量历史折叠
- [CSV / HDF5 / FlatPack](07-csv-hdf5-flatpack.md) — 持久化链的 snapshot 有时用 HDF5 存储，与链读取组合实现快速启动
- [tm_transport 共享链](../tm_transport/04-shared-chains.md) — etcd / Redis / RocksDB 链实现，接口与 InMemory 系列完全兼容
