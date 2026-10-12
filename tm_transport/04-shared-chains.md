---
title: 共享链后端（Shared Chain Backends）
library: tm_transport
headers: [tm_kit/transport/SharedChainCreator.hpp, tm_kit/transport/etcd_shared_chain/EtcdChain.hpp, tm_kit/transport/redis_shared_chain/RedisChain.hpp, tm_kit/transport/lock_free_in_memory_shared_chain/LockFreeInBoostSharedMemoryChain.hpp]
keywords: [SharedChainCreator, SharedChainProtocol, AllChainComponents, EtcdChain, RedisChain, LockFreeInBoostSharedMemoryChain, EtcdChainComponent, RedisChainComponent, SharedMemoryChainComponent, 共享链, 事件溯源, 链复制, 分布式一致性, headKey, dataPrefix, useNotification]
---

# 共享链后端（Shared Chain Backends）

## 用途

[`simple_shared_chain`](../tm_basic/08-shared-chain.md) 提供了"append-only 日志 + 折叠出状态"的抽象，但**只定义了内存实现**。本章的 `SharedChainCreator` 把同一个抽象接到**外部存储后端**，从而实现：

- **跨进程/跨机共享** —— 多个进程读同一条链，看到同样的历史与状态
- **持久化** —— 进程重启后链仍在
- **回测复现** —— 把实时写入的链在回测中从头读取

四种后端，用 protocol 前缀选择：

| protocol 字符串 | 后端 | 一致性模型 | 持久化 |
|---|---|---|---|
| `etcd` | Etcd（可配合 Redis 做数据平面） | 强一致（Raft） | ✓ |
| `redis` | Redis | 最终一致 | ✓（可配 TTL） |
| `in_memory_with_lock` | 进程内，带锁 | 单进程 | ✗ |
| `in_memory_lock_free` | 进程内，无锁 | 单进程 | ✗ |
| `in_shared_memory_with_lock` | Boost 共享内存，带锁 | 同机多进程 | ✗（进程全退即丢） |
| `in_shared_memory_lock_free` | Boost 共享内存，无锁 | 同机多进程 | ✗ |
| `empty` | 空实现 | —— | ✗（用于占位/测试） |

## 头文件与命名空间

```cpp
#include <tm_kit/transport/SharedChainCreator.hpp>

namespace dev::cd606::tm::transport
```

各后端配置类在其子目录中。

## 核心类型与签名

### 1. `SharedChainProtocol`（`SharedChainCreator.hpp:34`）

```cpp
enum class SharedChainProtocol {
    Etcd, Redis, InMemoryWithLock, InMemoryLockFree,
    InSharedMemoryWithLock, InSharedMemoryLockFree, Empty
};
inline const std::array<std::string,7> SHARED_CHAIN_PROTOCOL_STR = {   // :42
    "etcd", "redis", "in_memory_with_lock", "in_memory_lock_free",
    "in_shared_memory_with_lock", "in_shared_memory_lock_free", "empty"
};
```

### 2. `AllChainComponents`（`SharedChainCreator.hpp:27`）

一次性接入全部链后端组件的 Environment 别名：

```cpp
using AllChainComponents = infra::Environment<
    infra::HiddenTimeDependencyComponent
    , etcd_shared_chain::EtcdChainComponent
    , redis_shared_chain::RedisChainComponent
    , lock_free_in_memory_shared_chain::SharedMemoryChainComponent
>;
```

注意包含 `infra::HiddenTimeDependencyComponent`——链的时间戳来自数据本身，而不是环境的时钟。这是链能在回测中忠实重放时序的前提。

> `HiddenTimeDependencyComponent` 现在**已无实际作用**：`tm_infra/tm_kit/infra/Environments.hpp:89` 的注释说明"隐藏时间依赖"在 top-down 模式下**已是默认开启**，要**关闭**才需要显式放入 `NoHiddenTimeDependencyComponent`。`AllChainComponents` 里保留它只是历史兼容。

### 3. `SharedChainCreator<App>`（`SharedChainCreator.hpp:254`）

**每个进程一个实例**，内部用 `std::unordered_map<std::string, ...>` 缓存已创建的链对象（`:257` 的 `getChain`），保证同名链在同一进程内只创建一次。

#### 3.1 `reader`

```cpp
// :1036 — 直接给 protocol + locator
template <class ChainData, class ChainItemFolder, class TriggerT=void
    , class ResultTransformer=void, bool ForceSeparateDataStorageIfPossible=false>
auto reader(
    typename App::EnvironmentType *env
    , SharedChainProtocol protocol
    , ConnectionLocator const &locator
    , basic::simple_shared_chain::ChainPollingPolicy const &pollingPolicy
        = basic::simple_shared_chain::ChainPollingPolicy()
    , std::optional<ByteDataHookPair> hookPair = std::nullopt
    , ChainItemFolder &&folder = ChainItemFolder {}
    , std::conditional_t<std::is_same_v<ResultTransformer,void>, bool, ResultTransformer> &&resultTransformer = ...
) -> typename ReaderAction<ChainItemFolder, TriggerT, ResultTransformer>::Result;

// :1059 — 用字符串形式的链定位符（`protocol://locator`）
template <class ChainData, class ChainItemFolder, class TriggerT=void
    , class ResultTransformer=void, bool ForceSeparateDataStorageIfPossible=false>
auto reader(
    typename App::EnvironmentType *env
    , std::string const &locatorStr
    , basic::simple_shared_chain::ChainPollingPolicy const &pollingPolicy = ...
    , std::optional<ByteDataHookPair> hookPair = std::nullopt
    , ChainItemFolder &&folder = ChainItemFolder {}
    , ... &&resultTransformer = ...
) -> shared_chain_utils::ImporterOrAction<App, ChainItemFolder, TriggerT, ResultTransformer>;
```

**关键**：`TriggerT` 是 `void` 时（默认）返回 **`Importer`**——纯推送，链一到新数据就发出。给了 `TriggerT` 时返回 **`Action<TriggerT, ResultType>`**——由外部触发读取，这在回测中更常见（由回测时钟驱动）。

#### 3.2 `writer`

```cpp
// :1128
template <class ChainData, class ChainItemFolder, class InputHandler
    , class IdleLogic=void, bool ForceSeparateDataStorageIfPossible=false>
auto writer(
    typename App::EnvironmentType *env
    , SharedChainProtocol protocol
    , ConnectionLocator const &locator
    , basic::simple_shared_chain::ChainPollingPolicy const &pollingPolicy = ...
    , InputHandler &&inputHandler = InputHandler {}
    , std::conditional_t<std::is_same_v<IdleLogic,void>, basic::VoidStruct, IdleLogic> &&idleLogic = ...
) -> /* IdleLogic 为 void 时是 OnOrderFacility，否则是 OnOrderFacilityWithExternalEffects */;
```

`IdleLogic` 为 `void`（默认）时返回 `OnOrderFacility<InputType, ResponseType>`；给了 `IdleLogic` 时返回带外部效果的版本，用于"链空转时也要广播状态"的场景。

#### 3.3 工厂形式：`readerFactory` / `writerFactory`

`reader`/`writer` 会**立即**创建链并返回节点；`readerFactory`/`writerFactory` 返回一个**延迟创建**的工厂闭包（`ImporterOrActionFactory<...>`），在真正被图用到时才实例化链。示例代码普遍用工厂形式。

```cpp
// :1227 — 延迟创建的 reader 工厂
template <class ChainData, class ChainItemFolder, class TriggerT=void
    , class ResultTransformer=void, bool ForceSeparateDataStorageIfPossible=false>
auto readerFactory(
    typename App::EnvironmentType *env
    , std::string const &locatorStr
    , basic::simple_shared_chain::ChainPollingPolicy const &pollingPolicy = ...
    , ChainItemFolder &&folder = ChainItemFolder {}
    , ... &&resultTransformer = ...
) -> ImporterOrActionFactory<ChainItemFolder, TriggerT, ResultTransformer>;

// :1207 — 带 hook 的版本（多一个 hookPair 参数）
auto readerFactoryWithHook(...);

// :1276 / :1242 — 对应 writer 版本
auto writerFactory(...);
auto writerFactoryWithHook(...);
```

`readerFactory` 内部把 `folder` 与 `resultTransformer` 用 `std::make_shared` 拷进闭包（`:1220–1221`），因此**同一个 factory 可以被多次调用**（每次都从拷贝构造）。

#### 3.4 便捷函数

```cpp
// :271 / :290 — 创建链数据源（返回 Sourceoid，可直接接进图）
template <class ChainData>
... chainDataSource(...);

// :309 / :321 / :340 — 其他链操作封装
```

`tm_examples/simple_demo_chain_version/executables/print_chain/main.cpp:36–49` 的用法：

```cpp
transport::SharedChainCreator<M> sharedChainCreator;

auto chainDataSource = basic::simple_shared_chain::createChainDataSource<
    R, ChainData
>(
    r
    , sharedChainCreator.template readerFactory<
        ChainData
        , main_program_logic::TrivialChainDataFolder
    >(
        env
        , chainLocatorStr          // 例如 "redis://127.0.0.1:6379:::my_chain"
    )
    , "input_chain"
);
```

### 4. 链定位符：`protocol://locator`

```cpp
// SharedChainCreator.hpp:99
inline std::string makeSharedChainLocator(SharedChainProtocol protocol, ConnectionLocator const &locator) {
    return SHARED_CHAIN_PROTOCOL_STR[static_cast<int>(protocol)] + "://" + locator.toSerializationFormat();
}
```

例如：`etcd://127.0.0.1:2379:::my_chain[useWatchThread=true]`。

### 5. 配置类与属性

#### Etcd（`SharedChainCreator.hpp:103` 的 `etcdChainConfigurationFromConnectionLocator`）

| 属性 | 默认 | 含义 |
|---|---|---|
| `headKey` | `"head"` | 指向链头的键名 |
| `saveDataOnSeparateStorage` | `"true"` | 数据存到独立的 Etcd 键（而非全塞在链头） |
| `useWatchThread` | `"false"` | 用后台线程 watch 而非轮询 |
| `dataPrefix` | `<identifier>_data` | 数据键前缀 |
| `extraDataPrefix` | `<identifier>_extra_data` | 附加数据键前缀 |
| `redisServerAddr` | `""` | 非空时把数据平面放到 Redis（Etcd 只管链头） |
| `redisTTLSeconds` | `"0"` | Redis 中数据的 TTL |
| `automaticallyDuplicateToRedis` | `"false"` | 自动把数据同步到 Redis |
| `identifier` | —— | `ChainPrefix` |

**Etcd + Redis 混合模式**是推荐的组合：Etcd 用 Raft 保证链头指针的强一致，Redis 存实际数据以获得高吞吐。

#### Redis（`SharedChainCreator.hpp:117`）

| 属性 | 默认 | 含义 |
|---|---|---|
| `headKey` | `"head"` | 链头键名 |
| `dataPrefix` | `<identifier>_data` | 数据键前缀 |
| `extraDataPrefix` | `<identifier>_extra_data` | 附加数据键前缀 |
| `identifier` | —— | `ChainPrefix` |

Redis 后端没有 `useWatchThread`——靠轮询。

#### 共享内存（`SharedChainCreator.hpp:424`–`:470`）

| 属性 | 默认 | 取值 | 含义 |
|---|---|---|---|
| `identifier` | —— | 任意段名 | **共享内存段名**（第 5 段） |
| `size` | 4 GiB | 字节数 | 段大小 |
| `useName` | `"false"` | `true`/`false` | 用 Boost 命名对象做异常恢复 |
| `dataLock` | `"named"` | `"named"` / 其他 | 数据区锁策略：`"named"` → 命名互斥量；**任何其他值** → 不加锁（`None`） |
| `extraDataLock` | `"named"` | `"named"` / `"spin"` / `"none"` | 附加数据区锁策略：命名互斥量 / 自旋锁 / 不加锁 |
| `useNotification` | `"false"` | `true`/`false` | 用通知机制而非轮询（更低延迟） |

取值来自 `SharedChainCreator.hpp:429`–`:431` 的三行解析：

```cpp
// tm_kit/transport/SharedChainCreator.hpp:429-431
bool dataLockIsNamedMutex = (locator.query("dataLock", "named") == "named");
std::string extraDataLockType = locator.query("extraDataLock", "named");
bool useNotification = (locator.query("useNotification", "false") == "true");
```

注意 `dataLock` 的判定是**布尔式**的（只认 `"named"`，其余全当 `None`），而 `extraDataLock` 是**字符串分支**（`"spin"` → `BoostSharedMemoryChainExtraDataProtectionStrategy::SpinLockProtected`；`"none"` → 不加锁；其余 → `NamedMutex`）。两者语义不对称，容易写错。

这些选择对应 `LockFreeInBoostSharedMemoryChain` 的两个策略模板参数（`identifier` 之外最影响性能的旋钮，定义在 `tm_transport/tm_kit/transport/lock_free_in_memory_shared_chain/LockFreeInBoostSharedMemoryChain.hpp:282`、`:245`）：

```cpp
// :282 — 数据区锁策略
enum class BoostSharedMemoryChainDataLockStrategy { None, NamedMutex, SpinLock };

// :245 — 附加数据保护策略（比上面多两个选项）
enum class BoostSharedMemoryChainExtraDataProtectionStrategy {
    DontSupportExtraData
    , LockFreeAndWasteMemory
    , MutexProtected
    , SpinLockProtected
    , Unsafe
};
```

对应的锁实现类型是 `BoostSharedMemoryChain_EmptyLock` / `BoostSharedMemoryChain_NamedMutexLock` / `BoostSharedMemoryChain_SpinLock`，由 `IPCMutexWrapperResolver`（`:258`、`:262`）等 resolver 按策略选出。

**怎么选**：生产者与消费者在不同进程且写入频繁 → 至少 `dataLock=named`；同机多进程且对延迟敏感 → `extraDataLock=spin`；确认只有一个写入者 → 全部 `none` 换取最低开销。`useName=true` 会让链在进程异常退出后能按名字恢复已有段，代价是额外的名字注册开销。

`LockFreeInBoostSharedMemoryChain.hpp` 还定义了 `LockFreeInBoostSharedMemoryChainException`、`IPCMutexWrapper`（及 `IPCMutexWrapperGuard` / `IPCMutexWrapperResolver`）等底层类型；正常使用不必直接接触，但异常类型在排查共享内存冲突时会出现在日志里。

## 最小可用示例

### 回测中读取链

来源：`tm_examples/simple_demo_chain_version/executables/print_chain/main.cpp:36–49`（已简化）

```cpp
using M = infra::SinglePassIterationApp<Env>;
using R = infra::AppRunner<M>;
R r(env);

transport::SharedChainCreator<M> sharedChainCreator;
auto chainDataSource = basic::simple_shared_chain::createChainDataSource<
    R, ChainData
>(
    r
    , sharedChainCreator.template readerFactory<
        ChainData
        , main_program_logic::TrivialChainDataFolder
    >(
        env
        , chainLocatorStr          // 例如 "redis://127.0.0.1:6379:::my_chain"
    )
    , "input_chain"
);
```

### 注册到进程的 Environment

```cpp
// 来源：tm_transport/tm_kit/transport/SharedChainCreator.hpp:27（已简化）
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::AllChainComponents,          // Etcd + Redis + 共享内存链组件
    transport::BoostUUIDComponent
>;
```

## 实时 / 回测行为差异

**共享链是 TM Kit 中"实时与回测衔接"最核心的机制**——这正是它放在 `tm_transport` 而不是 `tm_basic` 的原因：链是跨进程/跨时间的通信媒介。

| 维度 | 实时 | 回测 |
|---|---|---|
| 写入 | 实时进程 append 到 Etcd/Redis | 回测通常**只读**，不写 |
| 读取 | 轮询或 watch，跟随链头前进 | 从头顺序读完，`TriggerT` 通常非 `void`（由回测时钟驱动） |
| 时间戳 | 由数据本身携带（`HiddenTimeDependencyComponent`） | 同左——这是链能忠实重放的前提 |
| 后端选择 | Etcd（一致性）或 Redis（吞吐） | 常用 Redis 或本地共享内存（快） |
| `pollingPolicy` | 影响延迟与 Etcd/Redis 负载 | 可设为"最快"以缩短回测时间 |
| `in_memory_*` | 仅单进程内有效 | 回测单进程时最方便，零外部依赖 |

**实务模式**：实时程序把业务事件 append 到 Etcd 链；回测程序用同一个 `ChainItemFolder` 从同一条链（或其快照副本）读出，重放出完全相同的状态序列。因为折叠逻辑（`ChainItemFolder`）是同一份代码，**回测与实时的状态演化必然一致**。

## 易错点

**1. `SharedChainCreator` 应按进程持有一个实例，不要每次调用新建**

它内部维护 `chains_` 缓存（`SharedChainCreator.hpp:257`），保证同名链只创建一次。如果每次 `reader`/`writer` 都新建一个 creator，会对同一个后端建多条独立连接，浪费资源并可能产生竞态。

**2. `TriggerT` 决定返回 Importer 还是 Action**

`TriggerT = void`（默认）→ `Importer`；给了 `TriggerT` → `Action<TriggerT, Result>`。这个差别是**编译期的**（`SharedChainCreator.hpp:128–141` 的 `ImporterOrActionTypeHelper`），写错会导致下游节点类型不匹配的编译错误。回测中由时钟驱动读取时通常需要非 `void` 的 `TriggerT`。

**3. Etcd 的 `saveDataOnSeparateStorage=false` 会把所有数据塞进链头键**

Etcd 单个 value 有大小限制（默认 1.5 MB）。数据量大时会把链头键撑爆，表现为写入失败。默认 `true`（`SharedChainCreator.hpp:107`）是安全的，不要随意关闭。

**4. Etcd 的属性名是**大小写敏感的 **camelCase**

`headKey`、`saveDataOnSeparateStorage`、`useWatchThread`、`dataPrefix`、`redisServerAddr`……（`SharedChainCreator.hpp:106–114`）。写 `head_key` 或 `HeadKey` 都会静默使用默认值——**不会报错**。

**5. 共享内存后端的 `identifier` 是段名，前 4 段地址无用**

与 [shared_memory_broadcast 传输](03-transports/shared_memory_broadcast.md) 相同：`identifier` 必须写在第 5 段，例如 `in_shared_memory_lock_free://:::my_chain[size=...]`。段大小默认为 4 GiB（`SharedChainCreator.hpp:426`）。

**6. `in_memory_*` 后端不能跨进程**

`InMemoryWithLock` / `InMemoryLockFree` 是**进程内**的。两个进程用同一个链名分别创建，会得到两条互不相干的链——不报错，只是各自演进。需要同机多进程共享用 `in_shared_memory_*`，跨机用 `etcd`/`redis`。

**7. 后端组件的缺失导致运行期异常而非编译错误**

`dispatch`（`SharedChainCreator.hpp:340` 附近）用 `std::is_convertible_v<Env*, XxxChainComponent*>` 判断后端是否可用。若 `TheEnvironment` 没有包含 `EtcdChainComponent` 而你用了 `etcd://`，会在运行期抛异常。用 `AllChainComponents` 可以一次性避免这个问题（代价是链接全部后端）。

**8. Redis 后端靠轮询，延迟取决于 `pollingPolicy`**

Redis 没有 watch 机制（与 Etcd 的 `useWatchThread` 对应）。对延迟敏感的场景用 Etcd + `useWatchThread=true`，或用共享内存 + `useNotification=true`。

**9. 链数据必须可序列化且跨版本兼容**

链上的数据要跨进程、跨时间读取。字段增删必须保持向后兼容（CBOR 的字段名映射支持这一点，但前提是数据是用带字段名的宏生成的）。改结构体字段名等于让历史数据读不出来。

## 第三方依赖

| 后端 | 库 | pkg-config | 官方文档 |
|---|---|---|---|
| Etcd | etcd-cpp-apiv3 | `libetcdcpp` | https://github.com/etcd-cpp-apiv3/etcd-cpp-apiv3 |
| Redis | hiredis / hiredis_ssl | `hiredis`, `hiredis_ssl`（可选） | https://github.com/redis/hiredis |
| 共享内存 | Boost.Interprocess | `boost` | https://www.boost.org/doc/libs/release/doc/html/interprocess.html |
| 全部 | gRPC（Etcd 客户端依赖） | `grpc` | https://grpc.io/docs/languages/cpp/ |

`tm_transport/meson.build:12` 声明 `etcd_dep = dependency('libetcdcpp')`。

Etcd 客户端本身通过 gRPC 与 Etcd 通信，因此**引入 Etcd 后端会连带引入 gRPC 的编译开销**。

## 相关章节

- [simple_shared_chain](../tm_basic/08-shared-chain.md) — 链的抽象、`ChainItemFolder`、`ChainPollingPolicy`
- [tm_transport 概览](00-overview.md) — `infra::Environment` 组件模型
- [Redis 传输](03-transports/redis.md) — Redis pub/sub（与 Redis 链共用 `RedisComponent`，但用途不同）
- [键值存储组件](07-kv-store-components.md) — `named_value_store` 的 Etcd/Redis 后端
- [时间与数据包装](../tm_infra/07-time-and-data.md) — `HiddenTimeDependencyComponent`
- [transaction v2](../tm_basic/09-transaction.md) — 事务型键值存储，与链是两种不同的状态管理方式
