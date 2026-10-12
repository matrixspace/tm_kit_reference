---
title: tm_transport 概览
library: tm_transport
headers: [tm_kit/transport/ConnectionLocator.hpp, tm_kit/transport/MultiTransportBroadcastListener.hpp, tm_kit/transport/MultiTransportRemoteFacility.hpp]
keywords: [tm_transport, ConnectionLocator, channel spec, 信道标识, AllNetworkTransportComponents, MultiTransport, 多传输抽象, 广播, broadcast, on-order facility, 远程设施, 传输能力矩阵]
---

# tm_transport 概览

## 用途

`tm_transport` 把"进程间通信"抽象成**两种角色**和**一套统一寻址**：

- **broadcast（广播）** —— 一对多、无响应。一个 publisher 发出，任意多个 listener 订阅。用于行情分发、心跳、状态通告。
- **on-order facility（按单设施）** —— 一对一、有响应。客户端发起请求（`Key<A>`），服务端返回响应（`KeyedData<A,B>`）。用于交易指令、查询、RPC。

两种角色都不绑定具体中间件。具体的传输方式（RabbitMQ / ZeroMQ / Redis / gRPC / WebSocket / ...）由**信道描述字符串**在运行期选择，业务代码只持有 `Source`/`Sink`/`FacilitioidConnector`，因此同一份图逻辑既能在 ZeroMQ 上跑，也能在 RabbitMQ 上跑，还能在回测中用内存合成设施替换。

这对量化系统的意义：**回测与实盘切换通信方式不需要改业务图**，只需要改信道字符串或改用 `SyntheticMultiTransportFacility`。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/ConnectionLocator.hpp>
#include <tm_kit/transport/MultiTransportBroadcastListener.hpp>          // 传输类型枚举 + 统一 listener 节点
#include <tm_kit/transport/MultiTransportBroadcastListenerManagingUtils.hpp>
#include <tm_kit/transport/MultiTransportBroadcastPublisherManagingUtils.hpp>
#include <tm_kit/transport/MultiTransportRemoteFacility.hpp>             // 统一 facility 节点
#include <tm_kit/transport/MultiTransportRemoteFacilityManagingUtils.hpp>
#include <tm_kit/transport/MultiTransportFacilityWrapper.hpp>
#include <tm_kit/transport/SyntheticMultiTransportFacility.hpp>

namespace dev::cd606::tm::transport
```

依赖链：`tm_infra` ← `tm_basic` ← `tm_transport`。链接目标为 `tm_kit_transport`（release）或 `tm_kit_transport_debug`（debug），通过 pkg-config 的 `tm_kit_transport` / `tm_kit_transport_debug` 解析。

## 核心类型与签名

### 1. `ConnectionLocator`（`tm_kit/transport/ConnectionLocator.hpp:17`）

统一的远端资源标识。所有传输共用同一个地址语法，这是"换中间件不改代码"的基础。

```cpp
class ConnectionLocator final {
public:
    ConnectionLocator() = default;
    ConnectionLocator(std::string const &h, int p);
    ConnectionLocator(std::string const &h, int p, std::string const &u, std::string const &pwd);
    ConnectionLocator(std::string const &h, int p, std::string const &u, std::string const &pwd, std::string const &id);

    static ConnectionLocator parse(std::string const &input);   // :43 解析字符串

    std::string const &host() const;        // :49
    int port() const;                       // :50
    std::string const &userName() const;    // :51
    std::string const &password() const;    // :52
    std::string const &identifier() const;  // :53

    std::string query(std::string const &field, std::string const &defaultValue="") const; // :55
    template <class F> void for_all_properties(F const &f) const;   // :57 遍历自定义属性

    std::string toSerializationFormat() const;  // :69
    std::string toPrintFormat() const;          // :70

    bool operator==(ConnectionLocator const &) const;   // :72
    bool operator<(ConnectionLocator const &) const;    // :73

    // 不可变修改器（返回新对象）
    ConnectionLocator modifyHost(std::string const &h) const;        // :75
    ConnectionLocator modifyPort(int p) const;                       // :80
    ConnectionLocator modifyUserName(std::string const &u) const;    // :85
    ConnectionLocator modifyPassword(std::string const &p) const;    // :90
    ConnectionLocator modifyIdentifier(std::string const &s) const;  // :95
    ConnectionLocator clearProperties() const;                       // :100
    ConnectionLocator removeProperty(std::string const &name) const;// :105
    ConnectionLocator addProperty(std::string const &name, std::string const &value) const; // :110
    ConnectionLocator addProperties(std::unordered_map<std::string,std::string> const &) const; // :115
};
```

**地址语法**（`src/ConnectionLocator.cpp:11` 的 `parse`）：

```
host:port:userName:password:identifier[prop1=value1,prop2=value2]
```

- 用 `:` 分隔，最多 5 段。**第 5 段（identifier）之后若还有 `:`，会被合并回 identifier**（`src/ConnectionLocator.cpp:32–39`），因此 identifier 本身可以含冒号（如 AMQP 的 `amq.topic` 不含冒号，但 routing key 常含）。
- 任一段可为空：`127.0.0.1::guest:guest:amq.topic` 表示 host=`127.0.0.1`、port=0、userName=`guest`、password=`guest`、identifier=`amq.topic`。
- 属性块用 `[...]` 包裹，逗号分隔 `name=value`。属性名**不能**是保留名 `HOST`/`PORT`/`USERNAME`/`USER`/`PASSWORD`/`PASSWD`/`IDENTIFIER`（大小写不敏感），重复属性会抛错。
- 解析失败抛 `ConnectionLocatorParseError`（`tm_kit/transport/ConnectionLocator.hpp:13`）。
- `query(field, default)` 先查属性块，再回退到保留字段；`query("HOST")` 等大小写敏感的保留名可读取基础字段。

`std::hash<ConnectionLocator>`（`tm_kit/transport/ConnectionLocator.hpp:132`）与 `operator<` 均已提供，可直接用作 `map`/`unordered_map` 的 key。

### 2. 信道描述字符串（channel spec）

信道字符串 = **传输名 + `://` + ConnectionLocator 字符串**。例如：

```
zeromq://localhost:12345
rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]
websocket://localhost:56789:::/data[ignoreTopic=true]
grpc_interop://localhost:50051
```

广播与 facility 各自维护一份**受支持的传输名列表**（`parseMultiTransportBroadcastChannel` 在 `tm_kit/transport/MultiTransportBroadcastListener.hpp:111`，`parseMultiTransportRemoteFacilityChannel` 在 `tm_kit/transport/MultiTransportRemoteFacility.hpp:60`）：

| 角色 | 支持的传输名（顺序即枚举序号） |
|---|---|
| broadcast | `multicast`, `rabbitmq`, `redis`, `nats`, `zeromq`, `nng`, `shared_memory_broadcast`, `websocket`, `singlecast` |
| on-order facility | `rabbitmq`, `redis`, `nats`, `socket_rpc`, `grpc_interop`, `json_rest`, `websocket` |

两者都返回 `std::optional<tuple<连接类型枚举, ConnectionLocator>>`：前缀不匹配返回 `nullopt`，前缀匹配但 locator 非法也返回 `nullopt`。

### 3. `AllNetworkTransportComponents`（`tm_kit/transport/MultiTransportBroadcastListener.hpp:31`）

一个把所有网络传输组件打包好的 `infra::Environment` 别名，方便"我要全部传输都能用"的场景：

```cpp
using AllNetworkTransportComponents = infra::Environment<
    multicast::MulticastComponent
    , rabbitmq::RabbitMQComponent
    , redis::RedisComponent
    , nats::NATSComponent
    , zeromq::ZeroMQComponent
    , nng::NNGComponent
    , shared_memory_broadcast::SharedMemoryBroadcastComponent
    , socket_rpc::SocketRPCComponent
    , grpc_interop::GrpcInteropComponent
    , json_rest::JsonRESTComponent
    , web_socket::WebSocketComponent
    , singlecast::SinglecastComponent
>;
```

`Environment` 是组件的虚继承混合，因此 `TheEnvironment` 通常写成：

```cpp
using TheEnvironment = infra::Environment<
    infra::CheckTimeComponent<false>,
    infra::TrivialExitControlComponent,
    basic::TimeComponentEnhancedWithSpdLogging<basic::real_time_clock::ClockComponent>,
    transport::AllNetworkTransportComponents,           // <- 一行接入全部传输
    transport::BoostUUIDComponent
>;
```

**代价**：`AllNetworkTransportComponents` 会把所有传输的第三方库都链接进二进制。生产环境通常只按需列出用到的组件（例如只列 `zeromq::ZeroMQComponent` 与 `rabbitmq::RabbitMQComponent`）。

### 4. 能力矩阵

| 传输 | 广播（listen/publish） | on-order facility | 备注 |
|---|---|---|---|
| `multicast` | ✓ | ✗ | UDP 组播，同网段；无 broker |
| `rabbitmq` | ✓ | ✓ | AMQP broker；支持 topic 通配 `#`/`*` |
| `zeromq` | ✓ | ✗ | 直连 pub/sub；无 broker |
| `redis` | ✓ | ✓ | pub/sub；topic 通配使用 Redis glob |
| `nats` | ✓ | ✓ | 轻量消息总线 |
| `nng` | ✓ | ✗ | 直连；见 `tm_kit/transport/nng/` |
| `shared_memory_broadcast` | ✓ | ✗ | 同机进程间共享内存；无网络开销 |
| `socket_rpc` | ✗ | ✓ | 裸 TCP 请求-响应 |
| `grpc_interop` | ✗ | ✓ | 对接外部 gRPC 服务；见 `tm_kit/transport/grpc_interop/` |
| `json_rest` | ✗ | ✓ | HTTP/JSON 客户端与文档服务器 |
| `websocket` | ✓ | ✓ | 双向；客户端与服务端设施 |
| `singlecast` | ✓ | ✗ | 单播广播，只送达一个订阅者 |

> 标 ✗ 的传输并非完全不能承载 facility：`SyntheticMultiTransportFacility` 可以用**两条广播信道**（请求一条、响应一条）在应用层合成请求-响应语义，从而让 facility 跑在 multicast / ZeroMQ / NNG 这类只有广播能力的传输上（示例见 `tm_examples/db_one_list_subscription/DBOneListSubscriptionServer.cpp:292`）。代价是失去了服务端的寻址与派发——所有响应对所有监听者可见。详见 [远程设施](02-facilities.md)。

### 5. 钩子（Hook）与身份校验（Identity）

两个横切概念贯穿全部传输：

- **`UserToWireHook` / `WireToUserHook`**（`tm_kit/transport/ByteDataHook.hpp`）——在序列化后的字节流上加解密、签名、压缩等变换。`UserToWireHook` 用于发送方向，`WireToUserHook` 用于接收方向，两者成对使用。
- **Identity checker 组件** —— `EmptyIdentityCheckerComponent`、`SimpleIdentityCheckerComponent`、`SignatureBasedIdentityCheckerComponent`（`tm_kit/transport/security/`）。决定"哪些远端客户端被允许连接"。

详见 [安全与身份校验](06-security.md)。

## 最小可用示例

### 发布端：一行接入两种传输

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:72–83`（已简化）

```cpp
using M = infra::RealTimeApp<TheEnvironment>;
using R = infra::AppRunner<M>;
R r(&env);

// 同一份数据发往 ZeroMQ 和 WebSocket 两个信道
auto publisherSink = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<basic::proto_interop::Proto, InputDataPOCO>(
        r
        , "input data publisher"
        , "zeromq://localhost:12345"
    );
auto publisherSink2 = transport::MultiTransportBroadcastPublisherManagingUtils<R>
    ::oneBroadcastPublisherWithProtocol<std::void_t, InputDataPOCO>(
        r
        , "input data publisher 2"
        , "websocket://localhost:56789:::/data[ignoreTopic=true]"
    );

r.connect(toPub.clone(), publisherSink);
r.connect(toPub.clone(), publisherSink2);
```

注意 `oneBroadcastPublisherWithProtocol<ProtocolWrapper, T>` 的 `ProtocolWrapper` 选 `std::void_t` 时表示"不用额外包装，直接 CBOR"；选 `basic::proto_interop::Proto` 时表示 wire 上走 protobuf。

### 订阅端：按信道字符串订阅

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:79–88`（已简化）

```cpp
auto heartbeatSource = transport::MultiTransportBroadcastListenerManagingUtils<R>
    ::oneBroadcastListener<transport::HeartbeatMessage>(
        r
        , "heartbeatListener"
        , "rabbitmq://127.0.0.1::guest:guest:amq.topic[durable=true]"
        , "simple_demo.plain_executables.#.heartbeat"   // topicDescription
    );
```

第 4 个参数 `topicDescription` 是传输相关的订阅过滤表达式（RabbitMQ 用 AMQP topic 通配，Redis 用 glob）；省略则用默认 topic（RabbitMQ 为 `#`，Redis 为 `*`，见 `tm_kit/transport/MultiTransportBroadcastListener.hpp:324` 的 `multiTransportListenerDefaultTopic`）。

## 实时 / 回测行为差异

`tm_transport` 的整体定位就是**只在实时模式下使用**。回测程序一般完全不链接它。

| 维度 | 实时（`RealTimeApp`） | 回测（`SinglePassIterationApp` / `TopDown`） |
|---|---|---|
| 传输节点可用性 | 全部可用 | `MultiTransportBroadcastListener`、`MultiTransportRemoteFacility` 均**硬编码为 `RealTimeApp<Env>`**（见 `tm_kit/transport/MultiTransportBroadcastListener.hpp:339`、`tm_kit/transport/MultiTransportRemoteFacility.hpp:123`），不能用于单程迭代 App |
| 数据来源 | 网络推送，自带后台线程 | 改用文件/内存 importer；或把实时图录制成 chain 再回放（见 `tm_examples/simple_demo_chain_version/`） |
| 时钟 | `real_time_clock::ClockComponent` | `single_pass_iteration_clock::ClockComponent`（数据的时间戳即"当前时间"） |
| 替代方案 | —— | `SyntheticMultiTransportFacility`（`tm_kit/transport/SyntheticMultiTransportFacility.hpp`）在内存中合成 facility，让同一份业务代码在没有网络的情况下跑通 |
| 连接重试 | 传输组件内部有重连逻辑（组件持有 `threadHandles()`） | 无此概念 |

实务做法：**把业务逻辑抽到独立的 `MainLogicCombination` 模板中**，实时可执行文件传入真实传输的 `Source`/`FacilitioidConnector`，回测可执行文件传入文件 importer 和合成设施——这正是 `tm_examples/simple_demo/` 的组织方式。

## 易错点

**1. 传输节点硬编码 `RealTimeApp`，放进回测 App 会编译失败**

`MultiTransportBroadcastListener` 的基类是 `infra::RealTimeApp<Env>::AbstractIntegratedOnOrderFacilityWithExternalEffects<...>`（`tm_kit/transport/MultiTransportBroadcastListener.hpp:339`），`MultiTransportRemoteFacility` 同样把 `M` 定为 `infra::RealTimeApp<Env>`（`tm_kit/transport/MultiTransportRemoteFacility.hpp:123`）。在 `SinglePassIterationApp` 的图里注册这些节点会得到一大堆模板实例化错误。回测请改用文件 importer 或合成设施。

**2. 信道字符串里的空段不能省**

`ConnectionLocator::parse` 用 `boost::split` 按 `:` 切分，空段会被保留为空串。写 `zeromq://localhost:12345` 得到 port=12345；写 `rabbitmq://127.0.0.1::guest:guest:amq.topic` 中 `127.0.0.1` 后面的空段把 port 设为 0（表示"用该传输的默认端口"）。若要指定端口又要指定用户名，必须写全 `host:port:user:pass`，不能跳过端口。

**3. 属性名与保留字段重名会抛异常**

`HOST`、`PORT`、`USERNAME`、`USER`、`PASSWORD`、`PASSWD`、`IDENTIFIER` 是保留属性名（`src/ConnectionLocator.cpp:78–82`），写进 `[...]` 会抛 `ConnectionLocatorParseError`。想改这些字段请用 `modifyHost`/`modifyPort` 等不可变修改器，或直接改地址串。

**4. 同一个 `ConnectionLocator` 属性顺序不影响相等性**

`properties_` 是 `std::map`，`operator==` 比较整个 map，因此 `[a=1,b=2]` 与 `[b=2,a=1]` 相等；但 `toSerializationFormat()` 按 map 顺序输出，两个逻辑上相同的 locator 可能产生不同的字符串。不要用序列化字符串做哈希键，用 `std::hash<ConnectionLocator>`。

**5. 广播与 facility 支持的传输集合不同**

`nng`、`zeromq`、`multicast`、`shared_memory_broadcast`、`singlecast` 只支持广播；`socket_rpc`、`grpc_interop`、`json_rest` 只支持 facility。把 `zeromq://...` 传给 `setupOneRemoteFacility` 会在运行期抛异常或静默返回 `nullopt`（`parseMultiTransportRemoteFacilityChannel` 返回 `nullopt`）。选传输前先查上面的能力矩阵。

**6. `oneBroadcastListener` 对不支持的 channel spec 直接抛 `std::runtime_error`**

与 `setupBroadcastListeners` 不同（后者容忍不支持的传输，因为 spec 可能来自网络），`oneBroadcastListener` 在无法建立监听时抛异常（`tm_kit/transport/MultiTransportBroadcastListenerManagingUtils.hpp:360`）。如果信道字符串来自配置文件，请选用 `setupBroadcastListeners` 族。

**7. 心跳与告警是所有传输的隐式前提**

服务发现（`setupBroadcastListenerThroughHeartbeat`、`setupOneNonDistinguishedRemoteFacility`）依赖心跳广播来决定"远端是否存在"。忘记调用 `initializeHeartbeatAndAlertComponent` 与 `attachHeartbeatAndAlertComponent` 会导致这些 setup 函数永远等不到对端。

## 第三方依赖

`tm_transport` 的依赖面很宽，但每个传输各管各的。顶层 `meson.build:4-18` 的依赖清单：

| 库 | pkg-config 名 | 用途 | 官方文档 |
|---|---|---|---|
| Boost | `boost` | Asio、Beast、Interprocess、UUID、Algorithm | https://www.boost.org/doc/libs/ |
| rabbitmq-c | `librabbitmq` | RabbitMQ 传输 | https://github.com/alanxz/rabbitmq-c |
| libzmq / cppzmq | `libzmq`, `cppzmq` | ZeroMQ 传输 | https://zeromq.org/ · https://github.com/zeromq/cppzmq |
| hiredis | `hiredis`, `hiredis_ssl`（可选） | Redis 传输与 Redis chain | https://github.com/redis/hiredis |
| nngpp | `nngpp` | NNG 传输 | https://github.com/nanomsg/nngpp |
| crossguid | `crossguid` | `CrossGuidComponent`（UUID 生成） | https://github.com/graeme-hill/crossguid |
| gRPC | `grpc` | gRPC interop | https://grpc.io/docs/languages/cpp/ |
| libetcd-cpp | `libetcdcpp` | Etcd chain 与 Etcd 命名值存储 | https://github.com/etcd-cpp-apiv3/etcd-cpp-apiv3 |
| SOCI | `soci` | `db_table_importer_exporter` | https://soci.sourceforge.net/ |
| libsodium | `libsodium` | 签名与加密 hook | https://doc.libsodium.org/ |
| curlpp | `curlpp` | JSON REST 客户端 | http://www.curlpp.org/ |
| IXWebSocket | `ixwebsocket` | WebSocket 传输 | https://github.com/machinezone/IXWebSocket |
| libnats | `libnats_static` | NATS 传输 | https://github.com/nats-io/nats.c |
| certify | 随仓库 `external/certify/` | TLS 证书处理 | https://github.com/djarek/certify |

**注意**：`libnats` 的 pkg-config 文件在本环境中被改为链接 `-lnats_static`（安装的静态库文件名是 `libnats_static.a`），见仓库根 `CLAUDE.md` 的 "Known Build Issues & Fixes"。此外 `grpc.pc` 被补上了 `-lgrpc++` 与 `Requires: grpc++`，因为 `tm_transport` 使用 gRPC 的 C++ API。

## 相关章节

- [广播：listener 与 publisher](01-broadcast.md) — `MultiTransportBroadcastListener`/`Publisher` 与 `ManagingUtils`
- [远程设施](02-facilities.md) — `MultiTransportRemoteFacility`、`FacilityWrapper`、`SyntheticMultiTransportFacility`
- [各传输详解](03-transports/) — 每个传输的 locator 语法、能力与第三方库
- [共享链后端](04-shared-chains.md) — Etcd / Redis / Boost 共享内存链
- [心跳与告警](05-heartbeat-and-alert.md) — 服务发现的基础设施
- [安全与身份校验](06-security.md) — Hook 与 identity checker
- [键值存储组件](07-kv-store-components.md) — `complex_key_value_store` / `named_value_store` / DB 表导入导出
- [AppRunner 连接与控制](../tm_infra/05-app-runner.md) — `registerImporter`、`connect`、`controlAll`
- [Environment 组件组合](../tm_infra/02-environments.md) — `infra::Environment` 的虚继承混合模型
