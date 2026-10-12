---
title: JsonREST 传输
library: tm_transport
headers: [tm_kit/transport/json_rest/JsonRESTComponent.hpp, tm_kit/transport/json_rest/JsonRESTClientFacility.hpp, tm_kit/transport/json_rest/JsonRESTFacilityWrapper.hpp, tm_kit/transport/json_rest/ComplexInput.hpp, tm_kit/transport/json_rest/RawString.hpp]
keywords: [json_rest, JsonRESTComponent, JsonRESTClientFacility, JsonRESTFacilityWrapper, ComplexInput, RawString, curlpp, HTTP, REST, JSON, setDocRoot, 前端, 浏览器, auth_token, parse_header, no_content_type, no_verify, use_curlpp, use_keep_alive_client]
---

# JsonREST 传输

## 用途

基于 **HTTP + JSON** 的传输。**只支持 on-order facility（HTTP 请求-响应），不支持广播**——`MultiTransportBroadcastListenerConnectionType`（`tm_kit/transport/MultiTransportBroadcastListener.hpp:89`）中没有它。

两个方向都能用：

- **作为服务端**：把 facility 暴露成 REST 端点，供浏览器、脚本、其他语言的服务调用。还能用 `setDocRoot` 同时托管静态文件（前端页面）。
- **作为客户端**：调用外部的 HTTP/JSON 服务（如交易所 REST API、第三方数据源）。

## 头文件与命名空间

```cpp
#include <tm_kit/transport/json_rest/JsonRESTComponent.hpp>
#include <tm_kit/transport/json_rest/JsonRESTClientFacility.hpp>
#include <tm_kit/transport/json_rest/JsonRESTFacilityWrapper.hpp>

namespace dev::cd606::tm::transport::json_rest
```

## 核心类型与签名

### 1. `JsonRESTComponent`

Environment 组件。除线程诊断外，提供静态文件托管：

```cpp
// 托管静态文件目录（前端页面）；port 上同时提供 REST 端点
env.transport::json_rest::JsonRESTComponent::setDocRoot(56788, "../simple_demo/plain_executables/datasource_web");
```

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:61`。

异常类型在 `JsonRESTComponentException.hpp`。

### 2. Locator 语法

```
json_rest://host:port:::/path[parse_header=false][auth_token=...][no_content_type=false][use_curlpp=false][no_verify=false][use_keep_alive_client=false]
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `host` / `port` | 监听（服务端）或目标（客户端）地址 | —— |
| `identifier` | **URL 路径**（如 `/configureMainLogic`） | —— |
| `parse_header` | 解析 HTTP 头并传递给业务逻辑 | `false`（`src/json_rest/JsonRESTComponent.cpp:113`） |
| `auth_token` | 客户端请求携带的 Bearer token | `""`（`:193`、`:1804`） |
| `no_content_type` | 不发 `Content-Type` 头 | `false`（`:204`） |
| `use_curlpp` | 客户端用 curlpp 而非内置实现 | `false`（`:1677`） |
| `no_verify` | 跳过 TLS 证书校验（**仅测试**） | `false`（`:1689`） |
| `use_keep_alive_client` | 客户端保持长连接 | `false`（`:1690`） |

服务端可以只写端口不写 host：`json_rest://:56788:::/key_query`（来源：`tm_examples/simple_demo/secure_executables/DataSource.cpp:159`）。

### 3. 客户端工厂：`JsonRESTClientFacilityFactory`

```cpp
// JsonRESTClientFacility.hpp:138
template <class Env>
class JsonRESTClientFacilityFactory {
public:
    // :141 — 输入包含 path/query/body 的复杂请求
    static auto createComplexInputClientFacility(...);

    // :219 — 复杂输入 + 附带数据
    static auto createComplexInputWithDataClientFacility(...);

    // :298 — 简单客户端 facility（请求体即 JSON，响应体即 JSON）
    static auto createClientFacility(...);
};
```

配套类型：

- `ComplexInput.hpp` —— 描述一个 HTTP 请求的 path / query 参数 / body 的结构
- `RawString.hpp` —— 把响应体当作未解析的字符串处理（对接非 JSON 的接口）

### 4. 服务端包装：`JsonRESTFacilityWrapper`

`JsonRESTFacilityWrapper.hpp` 提供把 facility 暴露为 REST 端点的包装器，用法与 `MultiTransportFacilityWrapper` 平行。

由于 HTTP 请求-响应模型与 facility 的 `Key<A>`/`KeyedData<A,B>` 不完全对应（HTTP 没有天然的请求 ID），REST 侧的包装对**身份**有额外要求——非字符串身份在 REST 下不被支持（见 `MultiTransportFacilityWrapper.hpp:219` 的报错信息："Json REST does not support facilities with non-string identity on input"）。

## 最小可用示例

### 服务端：把 facility 暴露为 REST 端点

来源：`tm_examples/simple_demo/plain_executables/MainLogic.cpp:118–131`（已简化）

```cpp
MainLogicInput<R> combinationInput {
    calc
    , {
        transport::MultiTransportFacilityWrapper<R>::facilityWrapperWithProtocol
            <basic::proto_interop::Proto, ConfigureCommandPOCO, ConfigureResultPOCO>(
            "rabbitmq://127.0.0.1::guest:guest:test_config_queue"
            , "cfg_wrapper_"
        )
        // 同一个 facility 同时暴露为 REST 端点 /configureMainLogic
        , transport::MultiTransportFacilityWrapper<R>::facilityWrapperWithProtocol
            <basic::nlohmann_json_interop::Json, ConfigureCommandPOCO, ConfigureResultPOCO>(
            "json_rest://0.0.0.0:34567:::/configureMainLogic"
            , "cfg_wrapper_2_"
        )
    }
    // ...
};
```

### 服务端：托管前端页面 + REST 端点

来源：`tm_examples/simple_demo/plain_executables/DataSource.cpp:61`、`:159`（已简化）

```cpp
TheEnvironment env;
// 在 56788 端口同时托管静态页面目录与 REST 端点
env.transport::json_rest::JsonRESTComponent::setDocRoot(56788, "../simple_demo/plain_executables/datasource_web");

// 把 keyQueryFacility 暴露为 POST /key_query，wire 上是 JSON
transport::MultiTransportFacilityWrapper<R>::wrapWithProtocol<
    basic::nlohmann_json_interop::Json, basic::VoidStruct, std::string>(
    r
    , keyQueryFacility
    , "json_rest://:56788:::/key_query"
    , "wrapper"
    , std::nullopt
    , false                     // dontAddToHeartbeat
);
```

注意这里用了 `dontAddToHeartbeat=false` 的显式写法（`wrapWithProtocol` 的第 6 个参数）。

### 客户端：调用外部 REST 服务

```cpp
// 来源：tm_kit/transport/json_rest/JsonRESTClientFacility.hpp:298 签名（示例代码库中暂无用例）
auto restFacility = transport::json_rest::JsonRESTClientFacilityFactory<TheEnvironment>
    ::template createClientFacility<RequestType, ResponseType>(
        "json_rest://api.example.com:443:::/v1/query[no_content_type=true][use_keep_alive_client=true]"
    );
```

## 实时 / 回测行为差异

| 维度 | 实时 | 回测 |
|---|---|---|
| 可用性 | ✓ | ✗ |
| 作为服务端 | 监听端口，接受外部调用 | 不适用 |
| 作为客户端 | 真实 HTTP 请求，受网络延迟与限流影响 | 应替换为本地 mock facility |
| 静态文件托管 | `setDocRoot` 可用 | 不适用 |
| 身份 | HTTP 无天然请求 ID，依赖 header 携带身份 | 不适用 |

**回测要点**：调用外部 REST API 的策略在回测中**必须**替换为本地 mock——否则既拿不到历史时点的数据（REST 返回的是"现在"），又会被限流。做法与 [远程设施](../02-facilities.md) 的 `if (isReal) ... else ...` 模式相同。

## 易错点

**1. 只有 facility，没有广播**

`json_rest://` 不能用于 `oneBroadcastListener`/`oneBroadcastPublisher`（`MultiTransportBroadcastListenerConnectionType` 中没有它，`tm_kit/transport/MultiTransportBroadcastListener.hpp:89`）。需要给前端推送数据用 [websocket](websocket.md)。

**2. REST 不支持非字符串身份**

如果环境配置了 identity checker 且请求类型不是 `std::string` 身份，`wrap` 会抛异常（`MultiTransportFacilityWrapper.hpp:219` 的报错信息："Json REST does not support facilities with non-string identity on input"）。REST 场景下把身份设计成字符串（如 API token 或用户名）。

**3. `identifier` 必须以 `/` 开头**

URL 路径是第 5 段。`json_rest://0.0.0.0:34567:::/configureMainLogic` 正确；`json_rest://0.0.0.0:34567:configureMainLogic` 会把路径当作用户名。

**4. `no_verify=true` 仅用于测试**

`src/json_rest/JsonRESTComponent.cpp:1689`。生产环境绝不能开。

**5. `parse_header=true` 会改变请求类型**

开启后 HTTP 头会被解析并传递给业务逻辑，`Request` 类型的结构随之变化。开关两侧的编译期类型不同，不能混用。

**6. 默认短连接，高频调用需开 `use_keep_alive_client`**

`use_keep_alive_client` 默认 `false`（`:1690`）。高频调用外部 REST API 时每次都要 TCP 握手 + TLS 握手，延迟显著。开启长连接可大幅降低开销。此外 `use_curlpp=false` 时用内置实现，某些认证/代理场景需要切到 curlpp（`:1677`）。

**7. HTTP 没有请求 ID，一次连接一次响应**

facility 的 `Key<A>` 语义依赖框架自己维护。如果服务端处理时间较长而客户端超时，重试会产生重复请求——**业务层必须幂等**。

**8. `setDocRoot` 与 REST 端点共用端口**

静态文件托管与 REST 端点在同一端口上（来源 `DataSource.cpp:61` 与 `:159` 都用 56788）。路径冲突时静态文件优先，可能导致 REST 端点被同名文件遮蔽。

## 第三方依赖

| 库 | pkg-config | 用途 | 官方文档 |
|---|---|---|---|
| curlpp | `curlpp` | 可选的 HTTP 客户端实现（`use_curlpp=true`） | http://www.curlpp.org/ |
| libcurl | 由 curlpp 传递依赖 | HTTP 传输 | https://curl.se/libcurl/ |
| nlohmann/json | 通过 `tm_basic` | JSON 序列化（`nlohmann_json_interop::Json<T>`） | https://json.nlohmann.me/ |
| Boost.Beast | `boost` | 内置 HTTP 服务端/客户端实现 | https://www.boost.org/doc/libs/release/libs/beast/ |
| OpenSSL | 传递依赖 | HTTPS | https://www.openssl.org/ |

`tm_transport/meson.build:16` 声明 `curlpp_dep = dependency('curlpp')`。

仓库根 `CLAUDE.md` 记录的相关 `.pc` 修补：无（curlpp 相关坑未记录）。

## 相关章节

- [远程设施](../02-facilities.md) — facility 客户端与服务端包装
- [websocket 传输](websocket.md) — 需要服务端推送时用这个
- [安全与身份校验](../06-security.md) — REST 场景下的身份设计
- [序列化格式](../../tm_basic/03-serialization.md) — `nlohmann_json_interop::Json<T>`
- [各传输能力矩阵](../00-overview.md)
