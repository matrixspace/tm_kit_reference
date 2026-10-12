---
title: 构建与安装
library: meta
headers: []
keywords: [构建, 编译, 安装, meson, ninja, vcpkg, pkg-config, build.sh, 环境变量, VCPKG_ROOT, BOOST_ROOT, PKG_CONFIG_PATH, INSTALL_PREFIX, BUILD_TYPE, NINJA_JOBS, .pc 修补, 链接错误]
---

# 构建与安装

本篇是 tm_infra / tm_basic / tm_transport 三库的构建与安装说明。上游仓库的 `CLAUDE.md` 有同一份内容，此处复制过来是为了让文档仓库**自包含**——独立 clone 或作为 submodule 挂到下游项目时，不必回头去找上游仓库。

## 1. 环境准备

构建分两步：先把环境脚本 source 进当前 shell，再跑统一的 `build.sh`。`build.sh` **刻意不自己准备工具链**，所以环境必须先 source。

从仓库根目录：

```bash
source ./build-env-setting-rocky.sh      # Rocky Linux 8.6 / gcc-toolset-15
# 或
source ./build-env-setting-centos.sh     # CentOS / devtoolset-10
```

`build-env-setting-rocky.sh` 设置的内容：

```bash
source /opt/rh/gcc-toolset-15/enable
export VCPKG_ROOT=/data1/dev/rockylinux8.6/vcpkg/
export PATH=${VCPKG_ROOT}/installed/x64-linux/tools/protobuf:$PATH
export PKG_CONFIG_PATH=/data1/dev/rockylinux8.6/tm_kit/lib64/pkgconfig:${VCPKG_ROOT}/installed/x64-linux/lib/pkgconfig:/usr/lib64/pkgconfig/
export BOOST_ROOT=${VCPKG_ROOT}/installed/x64-linux
```

> ⚠️ `PKG_CONFIG_PATH` **第一个条目**是 tm_kit 自己的安装前缀。下游项目靠它找到 `tm_kit_infra_debug`、`tm_kit_basic_debug` 等 `.pc`。**如果安装前缀与这个路径不一致，依赖解析必然失败。**

## 2. 构建

```bash
source ./build-env-setting-rocky.sh
./build.sh <project>          # tm_infra | tm_basic | tm_transport | tm_examples
```

**按依赖顺序构建**：`tm_infra` → `tm_basic` → `tm_transport` → `tm_examples`。

### build.sh 的环境变量

| 变量 | 默认 | 作用 |
|---|---|---|
| `BUILD_TYPE` | `debug` | `debug` / `debugoptimized` / `release` / `minsize` / `plain` |
| `INSTALL_PREFIX` | `/usr/local` | 安装位置，**必须与 `PKG_CONFIG_PATH` 一致** |
| `NINJA_JOBS` | `4` | 并行编译数（系统资源限制，不是建议值） |
| `VCPKG_TRIPLET` | `x64-linux` | vcpkg triplet |
| `NO_INSTALL` | 未设置 | 设为 `1` 则只构建不安装 |
| `ASSUME_YES` | 未设置 | 设为 `1` 跳过交互确认（隐含 clean rebuild） |

```bash
./build.sh tm_infra
BUILD_TYPE=release ./build.sh tm_basic
INSTALL_PREFIX=/data1/dev/rockylinux8.6/tm_kit ./build.sh tm_transport
ASSUME_YES=1 ./build.sh tm_examples          # 非交互，clean rebuild
```

### build.sh 做了什么

1. 打印检测到的工具链，并在 `VCPKG_ROOT` / `BOOST_ROOT` / `PKG_CONFIG_PATH` 未设置时警告
2. 请求确认；若 `builddir_<type>` 已存在，询问 **1) clean rebuild / 2) incremental / 3) abort**
3. 跑 `meson setup`（增量时用 `--reconfigure`），带 `--buildtype` / `--prefix` / `--cmake-prefix-path`
4. 跑 `ninja -j${NINJA_JOBS}`
5. 校验每个声明的目标文件确实存在于磁盘上
6. 对 tm_infra / tm_basic / tm_transport：请求确认后安装（前缀不可写时用 `sudo`），并校验 `.pc` 文件已落到前缀

**每一步都双重校验**——退出码**和**输出里的错误标记——因为 meson 与 ninja 都可能在报告错误后仍以 0 退出。日志写到 `<project>/build_<buildtype>.log`。

> **注意**：`tm_examples` **没有 install 目标**，可执行文件留在 `builddir_<buildtype>/` 里。

## 3. 手动构建（绕过 build.sh）

```bash
source ./build-env-setting-rocky.sh
cd <project_dir>

meson setup builddir_release --buildtype=release \
  --prefix=/usr/local \
  --cmake-prefix-path=/data1/dev/rockylinux8.6/vcpkg/installed/x64-linux

ninja -j4 -C builddir_release

# 仅 tm_infra / tm_basic / tm_transport
sudo ninja -j4 -C builddir_release install
```

**务必用 `ninja -j4`** 限制并行度。

## 4. 清洁重建

改了 `.pc` 文件或遇到依赖问题时，在 `build.sh` 的提示处选 **1) clean rebuild**（或设 `ASSUME_YES=1`，它总是选 clean）。手动清理：

```bash
rm -rf <project>/builddir_release <project>/builddir_debug
```

**Meson 在 configure 阶段缓存依赖信息**，所以改了 `.pc` 必须完整 reconfigure，只重跑 ninja 不会生效。

## 5. vcpkg 的 `.pc` 文件修补

多个 vcpkg 库的 `.pc` 不完整，已在下述路径中修补：`/data1/dev/rockylinux8.6/vcpkg/installed/x64-linux/lib/pkgconfig/`

完整清单与逐条说明见 [THIRD_PARTY.md](THIRD_PARTY.md) 第 2 节。摘要：

| 文件 | 问题 | 修补 |
|---|---|---|
| `crossguid.pc` | libcrossguid.a 用了 libuuid 未声明 | Libs 加 `-luuid` |
| `grpc.pc` | 只声明 C 库，tm_transport 用 C++ API | Libs 加 `-lgrpc++`；Requires 加 `grpc++` |
| `soci.pc` | SOCI 4.1.4 无 pkg-config 文件 | 从零创建 |
| `rocksdb.pc` | 压缩依赖未声明 | Requires 加 `liblz4`；Libs 加 `-lbz2` |
| `odbc.pc` | `-lltdl` 被 `--as-needed` 丢弃 | 改绝对路径 `${libdir}/libltdl.a` |
| `tclap.pc` | header-only，无 `.pc` | 从零创建，仅 Cflags |
| `libnats.pc` | 实际库名是 `libnats_static.a` | `-lnats` → `-lnats_static` |
| `mongoc2-static.pc` | 调 `utf8proc_NFKC` 未声明依赖 | Requires 加 `libutf8proc` |

### 两条通用规则

**规则一：传递依赖放 `Requires:`，不要放 `Libs:`。**
A.pc 把 `-lB` 写在 `Libs:` 里时，pkg-config **不会**读 B.pc，也就不会展开 B 自己的依赖链。只有 `Requires: B` 会拉入 B 的完整 Cflags 与 Libs。这条修好了 `soci → odbc → libltdl.a` 与 `soci → mysqlclient`（`mysql.h` 的 include 路径）两个问题。

**规则二：meson 的 `--as-needed` 丢弃 `-l` 形式的库时，改用绝对路径。**
写 `${libdir}/libfoo.a` 绕过。**改之前先核对库名与磁盘上的文件名一致**——`libnats` vs `libnats_static` 就是这么踩的。

### 排查链接错误

```bash
# 1. .pc 能否被找到
pkg-config --exists <name> && echo found
# 2. Cflags / Libs
pkg-config --cflags <name>
pkg-config --libs <name>
# 3. 缺的符号在哪个 .a 里
pkg-config --libs <name> | tr ' ' '\n' | grep <symbol-lib>
# 4. 磁盘上真的有这个 .a 吗（核对名字）
ls ${VCPKG_ROOT}/installed/x64-linux/lib/ | grep <name>
```

## 6. 下游项目怎么用

在 `meson.build` 里通过 pkg-config 引入：

```meson
project('my_tm_app', 'cpp', default_options: ['cpp_std=c++17'])

if get_option('buildtype') == 'debug'
    tm_infra_dep     = dependency('tm_kit_infra_debug')
    tm_basic_dep     = dependency('tm_kit_basic_debug')
    tm_transport_dep = dependency('tm_kit_transport_debug')
else
    tm_infra_dep     = dependency('tm_kit_infra')
    tm_basic_dep     = dependency('tm_kit_basic')
    tm_transport_dep = dependency('tm_kit_transport')
endif

executable('my_app', 'main.cpp',
    dependencies: [tm_infra_dep, tm_basic_dep, tm_transport_dep])
```

```bash
source ./build-env-setting-rocky.sh
meson setup builddir --buildtype=debug \
  --prefix=/data1/dev/rockylinux8.6/tm_kit \
  --cmake-prefix-path=/data1/dev/rockylinux8.6/vcpkg/installed/x64-linux
ninja -j4 -C builddir
```

调试 `.pc` 解析：

```bash
pkg-config --exists tm_kit_basic_debug && echo found
pkg-config --cflags tm_kit_basic_debug
pkg-config --libs   tm_kit_basic_debug | tr ' ' '\n' | head -20
```

## 7. 编译开销

**gRPC + Abseil + protobuf 是编译时间与日志体积的主要来源。** debug 构建日志可达 ~1 GB，主因是这两个库的模板实例化与弃用警告。

- 用定向 `grep` 查日志，不要整file读：
  ```bash
  grep -n '^FAILED:' build_debug.log                       # 失败的构建目标
  grep -n 'error:' build_debug.log | grep -v 'warning:'    # 真正的错误
  ```
- **生产项目不要用 `AllNetworkTransportComponents`**——它把所有传输的第三方库都链进来。按需列出用到的组件。
- 同理 `AllChainComponents` 会连带引入 Etcd → gRPC。

## 8. 编译器要求

- GCC >= 9.3.1（本环境用 gcc-toolset-15 / GCC 15.2.1）
- C++17
- Meson 1.11.1（本环境）
- Boost 1.91.0（静态，经 vcpkg）

## 9. 相关章节

- [THIRD_PARTY.md](THIRD_PARTY.md) —— 第三方库总表与 8 处 `.pc` 修补的完整说明
- [QUICK_START.md](QUICK_START.md) —— 从零写第一个程序
- [DOWNSTREAM.md](DOWNSTREAM.md) —— 下游项目接入本套文档
- [PATTERNS.md](PATTERNS.md) —— 构建相关的易错点（§7）
