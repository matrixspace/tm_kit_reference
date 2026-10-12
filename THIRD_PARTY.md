---
title: 第三方库总表
library: meta
headers: []
keywords: [第三方库, third party, 依赖, vcpkg, pkg-config, Boost, gRPC, SOCI, RocksDB, protobuf, spdlog, nlohmann_json, simdjson, HDF5, hiredis, libzmq, rabbitmq-c, libsodium, curlpp, IXWebSocket, libnats, nng, etcd, crossguid, certify, tclap, date_tz, meson, ninja, .pc 修补]
---

# 第三方库总表

本表汇总全套文档各章节"第三方依赖"小节的内容，回答两个问题：**这个库用在哪**、**出问题去哪查**。

构建方式见仓库根 `CLAUDE.md`。依赖全部通过 **vcpkg** 安装在 `/data1/dev/rockylinux8.6/vcpkg/installed/x64-linux/`，以 **pkg-config 为主、CMake 为辅**解析。

## 1. 按库索引

### 1.1 基础设施

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **Boost** 1.91.0（静态） | `boost` | Asio、Beast、Interprocess、Hana、Preprocessor、Endian、LexicalCast、Log、UUID、Algorithm | https://www.boost.org/doc/libs/ | 几乎所有章节 |
| **Protocol Buffers** | 由 gRPC 传递依赖 | `Proto<T>` 序列化 | https://protobuf.dev/ | [tm_basic/03](tm_basic/03-serialization.md) |
| **spdlog** | `spdlog` | 日志后端 | https://github.com/gabime/spdlog · https://spdlog.docsforge.com/ | [tm_basic/04](tm_basic/04-logging.md) |
| **crossguid** | `crossguid` | UUID 生成（`CrossGuidComponent`） | https://github.com/graeme-hill/crossguid | [tm_transport/00](tm_transport/00-overview.md) |

### 1.2 序列化与数据格式

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **nlohmann_json** | `nlohmann_json` | JSON 编解码主路径 | https://github.com/nlohmann/json · https://json.nlohmann.me/ | [tm_basic/03](tm_basic/03-serialization.md) |
| **simdjson** | `simdjson` | 快速 JSON 解码（`read_simd`） | https://simdjson.org/ · https://github.com/simdjson/simdjson/blob/master/doc/basics.md | [tm_basic/03](tm_basic/03-serialization.md) |
| **HDF5**（含 C++ API） | `hdf5[cpp]` | 列存批量 I/O | https://docs.hdfgroup.org/hdf5/develop/ · [C++ API](https://docs.hdfgroup.org/hdf5/develop/group___h5_c_p_p.html) | [tm_basic/07](tm_basic/07-csv-hdf5-flatpack.md) |

> **simdjson 无独立框架头文件**——由 `NlohmannJsonInterop.hpp:28` 的 `#include <simdjson.h>` 引入。Windows 下 vcpkg 的 simdjson 需额外链接 `simdjson.cpp`，见 `tm_basic/README.md:39`。

### 1.3 数据库与存储

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **SOCI** 4.1.4 | `soci` ⚠️ | 数据库抽象（sqlite3 / mysql / odbc / postgresql） | https://soci.sourceforge.net/ | [tm_basic/09](tm_basic/09-transaction.md)、[tm_transport/07](tm_transport/07-kv-store-components.md) |
| **SQLite3** | 由 SOCI 传递依赖 | SQLite 后端 | https://www.sqlite.org/ | 同上 |
| **MySQL client** | 由 SOCI 传递依赖 | MySQL 后端 | https://dev.mysql.com/doc/c-api/ | 同上 |
| **PostgreSQL libpq** | 由 SOCI 传递依赖 | PostgreSQL 后端 | https://www.postgresql.org/docs/current/libpq.html | 同上 |
| **unixODBC / libltdl** | `odbc` ⚠️ | ODBC 后端 | https://www.unixodbc.org/ | 同上 |
| **RocksDB** | `rocksdb` ⚠️ | 嵌入式 KV 存储（链后端） | https://rocksdb.org/ | [BUILD.md](BUILD.md) |
| **etcd-cpp-apiv3** | `libetcdcpp` | Etcd 链与命名值存储 | https://github.com/etcd-cpp-apiv3/etcd-cpp-apiv3 | [tm_transport/04](tm_transport/04-shared-chains.md)、[07](tm_transport/07-kv-store-components.md) |

### 1.4 网络传输

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **rabbitmq-c** | `librabbitmq` | RabbitMQ 传输 | https://github.com/alanxz/rabbitmq-c | [03-transports/rabbitmq](tm_transport/03-transports/rabbitmq.md) |
| **libzmq** + **cppzmq** | `libzmq`, `cppzmq` | ZeroMQ 传输 | https://zeromq.org/ · https://libzmq.readthedocs.io/ · https://github.com/zeromq/cppzmq | [03-transports/zeromq](tm_transport/03-transports/zeromq.md) |
| **hiredis**（+ `hiredis_ssl` 可选） | `hiredis`, `hiredis_ssl` | Redis 传输与 Redis 链 | https://github.com/redis/hiredis | [03-transports/redis](tm_transport/03-transports/redis.md) |
| **libnats**（nats.c） | `libnats_static` ⚠️ | NATS 传输 | https://github.com/nats-io/nats.c · https://docs.nats.io/ | [03-transports/nats](tm_transport/03-transports/nats.md) |
| **nngpp**（内含 NNG） | `nngpp` | NNG 传输 | https://github.com/nanomsg/nngpp · https://nng.nanomsg.org/ | [03-transports/nng](tm_transport/03-transports/nng.md) |
| **gRPC**（C++） | `grpc` ⚠️ | gRPC interop 传输 | https://grpc.io/docs/languages/cpp/ | [03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md) |
| **Abseil** | 由 gRPC 传递依赖 | gRPC 基础库 | https://abseil.io/ | 同上 |
| **curlpp** + **libcurl** | `curlpp` | JSON REST 客户端 | http://www.curlpp.org/ · https://curl.se/libcurl/ | [03-transports/json_rest](tm_transport/03-transports/json_rest.md) |
| **IXWebSocket** | `ixwebsocket` | WebSocket 传输（可选后端） | https://github.com/machinezone/IXWebSocket | [03-transports/websocket](tm_transport/03-transports/websocket.md) |

### 1.5 安全

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **libsodium** | `libsodium` | 签名、验签、加密 hook | https://doc.libsodium.org/ | [tm_transport/06](tm_transport/06-security.md) |
| **OpenSSL** | 各传输传递依赖 | TLS | https://www.openssl.org/ | [tm_transport/06](tm_transport/06-security.md) |
| **certify** | 随仓库 `tm_transport/external/certify/` | TLS 证书处理 | https://github.com/djarek/certify | [tm_transport/06](tm_transport/06-security.md) |

### 1.6 时间

| 库 | pkg-config | 用途 | 官方文档 | 涉及文档 |
|---|---|---|---|---|
| **date/tz**（Howard Hinnant） | `date[tz]` | IANA 时区（`dateHolderFromZonedTimePoint`） | https://howardhinnant.github.io/date/tz.html | [tm_basic/06](tm_basic/06-value-types.md) |

> 仅在使用时区转换时才需要。`DateHolder` 的本地/UTC 版本不依赖它。

### 1.7 构建工具

| 工具 | 版本 | 用途 | 官方文档 |
|---|---|---|---|
| **Meson** | 1.11.1（本环境） | 构建配置 | https://mesonbuild.com/ |
| **Ninja** | —— | 构建执行（**必须 `-j4`**） | https://ninja-build.org/ |
| **pkg-config** | —— | 依赖解析主路径 | https://www.freedesktop.org/wiki/Software/pkg-config/ |
| **vcpkg** | —— | 依赖包管理 | https://vcpkg.io/ |

## 2. 本环境的 `.pc` 修补（8 处）

vcpkg 提供的若干 `.pc` 文件不完整。仓库根 `CLAUDE.md` 记录了全部修补，此处汇总并标注影响范围。**带 ⚠️ 的表项即对应下面的条目。**

| # | 文件 | 问题 | 修补 | 影响文档 |
|---|---|---|---|---|
| 1 | `crossguid.pc` | libcrossguid.a 用了 libuuid 但未声明 | Libs 加 `-luuid` | [tm_transport/00](tm_transport/00-overview.md) |
| 2 | `grpc.pc` | 只声明 C 库，但 tm_transport 用 C++ API | Libs 加 `-lgrpc++`；Requires 加 `grpc++` | [03-transports/grpc_interop](tm_transport/03-transports/grpc_interop.md) |
| 3 | `soci.pc` | SOCI 4.1.4 只提供 CMake config，**无 pkg-config 文件** | 从零创建：`Requires: fmt odbc mysqlclient`，`Libs: -lsoci_sqlite3 -lsoci_mysql -lsoci_odbc -lsoci_postgresql -lsoci_core -lsqlite3 -lpq` | [07-kv-store-components](tm_transport/07-kv-store-components.md) |
| 4 | `rocksdb.pc` | 压缩依赖未声明 | Requires 加 `liblz4`；Libs 加 `-lbz2` | 链后端 |
| 5 | `odbc.pc` | `-lltdl` 被 meson 的 `--as-needed` 丢弃 | 改为绝对路径 `${libdir}/libltdl.a` | [07-kv-store-components](tm_transport/07-kv-store-components.md) |
| 6 | `tclap.pc` | tclap 1.2.5 是 header-only，无 `.pc` | 从零创建，仅 Cflags | tm_examples |
| 7 | `libnats.pc` | 安装的静态库是 `libnats_static.a`，`-lnats` 找不到 | `-lnats` 改为 `-lnats_static` | [03-transports/nats](tm_transport/03-transports/nats.md) |
| 8 | `mongoc2-static.pc` | libmongoc2.a 调用 `utf8proc_NFKC` 但未声明依赖 | Requires 加 `libutf8proc` | —— |

### 2.1 两条通用规则

**规则一：传递依赖放 `Requires:`，不要放 `Libs:`。**

当 A.pc 直接把 `-lB` 写在 `Libs:` 里，pkg-config **不会**去读 B.pc，因此不会展开 B 自己的依赖链。只有 `Requires: B` 才会拉入 B 的完整 Cflags 与 Libs。

这条规则解决了两个具体问题：
- `soci → odbc → libltdl.a`（ltdl 链接失败）
- `soci → mysqlclient`（`mysql.h` 的 include 路径 `include/mysql` 缺失）

**规则二：meson 的 `--as-needed` 会丢弃 `-l` 形式的库时，改用绝对路径。**

写成 `${libdir}/libfoo.a` 可绕过。这是 `odbc.pc` 的 libltdl 修补的做法。同理，**先确认库名与磁盘上的文件名一致**再改 `.pc`——`libnats` 与 `libnats_static` 就是这个坑。

### 2.2 改完 `.pc` 必须完整重配置

Meson 在 **configure 阶段**缓存依赖信息，仅重跑 ninja 不会拾取 `.pc` 的修改。改完 `.pc` 后：

```bash
source ./build-env-setting-rocky.sh
ASSUME_YES=1 ./build.sh <project>     # ASSUME_YES 隐含 clean rebuild
```

### 2.3 排查链接错误的流程

遇到 "undefined reference" 时按顺序检查：

```bash
# 1. 该库的 .pc 能否被找到
pkg-config --exists <name> && echo found

# 2. 它的 Cflags / Libs 是什么
pkg-config --cflags <name>
pkg-config --libs <name>

# 3. 缺的符号在哪个 .a 里
pkg-config --libs <name> | tr ' ' '\n' | grep <symbol-lib>

# 4. 磁盘上真的有这个 .a 吗（核对名字！）
ls /data1/dev/rockylinux8.6/vcpkg/installed/x64-linux/lib/ | grep <name>
```

## 3. 依赖链与构建顺序

```
tm_infra  ──►  tm_basic  ──►  tm_transport
   │              │                │
   │              │                └─► tm_examples
   │              └──────────────────┘
   └─────────────────────────────────┘
```

- 三库均可安装（`INSTALL_PREFIX`，默认 `/usr/local`），并导出 `.pc` 文件供下游解析
- `tm_examples` **无 install 目标**，可执行文件留在 `builddir_<type>/`
- `PKG_CONFIG_PATH` **必须**包含 tm_kit 的安装前缀（`build-env-setting-rocky.sh` 里排在最前），否则下游找不到 `tm_kit_infra_debug` / `tm_kit_basic_debug` / `tm_kit_transport_debug`

构建顺序：`tm_infra` → `tm_basic` → `tm_transport` → `tm_examples`。

## 4. 编译开销提示

**gRPC + Abseil + protobuf 是编译时间与日志体积的主要来源。** 仓库根 `CLAUDE.md` 提到 debug 构建日志可达 ~1 GB，主因是这两个库的模板实例化与弃用警告。

实务建议：

- 用 `NINJA_JOBS=4`（默认）限制并行度——这是**系统资源约束**，不是性能调优
- 日志用定向 `grep`，不要整file读：
  ```bash
  grep -n '^FAILED:' build_debug.log                       # 失败的构建目标
  grep -n 'error:' build_debug.log | grep -v 'warning:'    # 真正的错误
  ```
- **不要在生产项目中用 `AllNetworkTransportComponents`**——它把所有传输的第三方库都链接进来。按需列出用到的组件（如只要 `zeromq::ZeroMQComponent` 与 `rabbitmq::RabbitMQComponent`）。
- 同理，`AllChainComponents` 会连带引入 Etcd → gRPC。

## 5. 相关章节

- [BUILD.md](BUILD.md) — 构建流程、`.pc` 修补的完整记录
- [tm_infra 概览](tm_infra/00-overview.md) — 核心库无第三方依赖
- [tm_basic 概览](tm_basic/00-overview.md) — 时钟、序列化、日志
- [tm_transport 概览](tm_transport/00-overview.md) — 各组件的依赖清单
- [QUICK_START](QUICK_START.md) — 从零搭建时的最小依赖集
