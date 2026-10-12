---
title: 序列化宏与结构反射
library: tm_basic
headers: [tm_kit/basic/SerializationHelperMacros.hpp, tm_kit/basic/StructFieldInfoHelper.hpp, tm_kit/basic/StructFieldInfoUtils.hpp, tm_kit/basic/StructFieldInfoHelper_Tuple.hpp, tm_kit/basic/StructFieldInfoHelper_NamedField.hpp, tm_kit/basic/ConcatStructFieldInfo.hpp, tm_kit/basic/StructFieldFlattenedInfo.hpp, tm_kit/basic/StructFieldInfoBasedCopy.hpp, tm_kit/basic/StructFieldInfoWithMaskingFilter.hpp]
keywords: [StructFieldInfo, StructFieldTypeInfo, StructFieldOffsetInfo, HasStructFieldInfo, TM_BASIC_CBOR_CAPABLE_STRUCT, TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE, TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES, TM_BASIC_CBOR_CAPABLE_EMPTY_STRUCT, TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT, TM_BASIC_CBOR_CAPABLE_ENUM_AS_STRING, PROTECT_TYPE, TM_SERIALIZATION_HELPER_COMMA_START_POS, EncDecWithFieldNames, REFERENCE_NAME, FIELD_NAMES, FIELD_OFFSETS, getFieldIndex, Boost.Preprocessor, 反射, 编译期反射, 序列化宏]
---

# 序列化宏与结构反射

## 用途

TM Kit 没有代码生成步骤，也不依赖 protoc。它用一族 Boost.Preprocessor 宏，从一份"字段清单"同时生成：结构体定义、比较运算、打印、CBOR 编解码，以及**编译期反射信息** `StructFieldInfo`。

反射信息是 tm_basic / tm_transport 中大量能力的基石：CSV 读写、HDF5 落盘、FlatPack、ProtoInterop、JSON 互操作、字段掩码、结构拷贝、哈希，全都是在 `StructFieldInfo` 之上做泛型展开，而不是为每个结构手写代码。因此理解本篇的契约，等于理解"为什么我的结构体能直接 CSV 导出"以及"为什么加了宏仍然不行"。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/SerializationHelperMacros.hpp>  // 宏族
#include <tm_kit/basic/StructFieldInfoHelper.hpp>      // 反射契约（三个 trait）
#include <tm_kit/basic/StructFieldInfoUtils.hpp>       // 初始化器、哈希

namespace dev::cd606::tm::basic                        // 三个 trait 所在
namespace dev::cd606::tm::basic::struct_field_info_utils // 工具
namespace dev::cd606::tm::basic::bytedata_utils        // macro_type_resolver
```

宏本身是全局的（无命名空间），但宏展开出的 trait 特化会自行打开 `dev::cd606::tm::basic` 命名空间，因此**宏必须在全局命名空间中调用**。

## 核心类型与签名

### 1. 三个反射 trait（契约）

```cpp
// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:8
template <class T>
class StructFieldInfo {
public:
    static constexpr bool HasGeneratedStructFieldInfo = false;   // :11
};

// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:13
template <class T, int Idx>
class StructFieldTypeInfo {};

// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:16
template <class T>
class StructFieldOffsetInfo {
public:
    static constexpr bool HasGeneratedStructFieldOffsetInfo = false;  // :19
};
```

特化后（由宏生成）的完整形状，见 `SerializationHelperMacros.hpp:906` 的 `_FIELD_INFO`：

```cpp
template <>
class StructFieldInfo<MyStruct> {
public:
    static constexpr bool HasGeneratedStructFieldInfo = true;              // :911
    static constexpr bool EncDecWithFieldNames = /* true | false */;       // :912
    static constexpr std::string_view REFERENCE_NAME = "MyStruct";         // :913
    static constexpr std::array<std::string_view, N> FIELD_NAMES = {...};  // :914
    static constexpr int getFieldIndex(std::string_view const &fieldName); // :917，未命中返回 -1
};

template <>
class StructFieldTypeInfo<MyStruct, Idx> {   // 每个字段一个特化，见 :890
public:
    using TheType = /* 字段类型 */;                              // :894
    static TheType       &access(MyStruct &d);                   // :895
    static TheType const &constAccess(MyStruct const &d);        // :898
    static TheType      &&moveAccess(MyStruct &&d);              // :901
};

template <>
class StructFieldOffsetInfo<MyStruct> {                          // :924
public:
    static constexpr bool HasGeneratedStructFieldOffsetInfo = true;        // :926
    static constexpr std::array<std::size_t, N> FIELD_OFFSETS = {...};     // :927，基于 offsetof
};
```

C++20 下另有一个 concept：

```cpp
// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:22-24
#if __cplusplus >= 202002L
template <class T>
concept HasStructFieldInfo = StructFieldInfo<T>::HasGeneratedStructFieldInfo;
#endif
```

### 2. 宏族的四层结构

读源码时容易迷失在两千多行宏里。实际只有四层：

| 层 | 作用 | 举例 |
|---|---|---|
| **字段表示** | 一个字段是 Boost.PP 二元组 `(类型, 名字)`；整张清单是 Boost.PP SEQ | `((int32_t, amount))` |
| **逐项宏** | 被 `BOOST_PP_SEQ_FOR_EACH` 对每个字段调用一次 | `_ITEM_DEF` :51、`_PRINT_ITEM` :79、`_EQ_ITEM` :84 |
| **单切面宏** | 生成一个"切面"（定义 / 比较 / 打印 / 编码 / 解码 / 反射） | `_STRUCT_DEF` :54、`_STRUCT_ENCODE` :183、`_STRUCT_FIELD_INFO` :906 |
| **顶层宏** | 开发者实际调用的，组合若干切面 | `TM_BASIC_CBOR_CAPABLE_STRUCT` :1015 |

模板参数清单也是 SEQ，元素是 `(种类, 名字)` 二元组，例如 `((typename, Env))`：`_TEMPLATE_DEF_LIST` :63 把它展开成 `typename Env`（用于 `template <...>`），`_TEMPLATE_USE_LIST` :67 展开成 `Env`（用于 `MyStruct<Env>`）。

### 3. 顶层宏对照表

按"结构形状 × 字段名模式"排列：

| 顶层宏 | 行号 | 生成内容 |
|---|---|---|
| `TM_BASIC_CBOR_CAPABLE_STRUCT(name, fields)` | :1015 | 定义 + `==` + `<` + 打印 |
| `..._STRUCT_SERIALIZE(name, fields)` | :1021 | CBOR 编解码（**带**字段名）+ 反射 |
| `..._STRUCT_SERIALIZE_NO_FIELD_NAMES(name, fields)` | :1026 | CBOR 编解码（**不带**字段名）+ 反射 |
| `..._EMPTY_STRUCT(name)` | ~:1031 | 空结构的定义 + 比较 + 打印 |
| `..._EMPTY_STRUCT_SERIALIZE(name)` | ~:1037 | 空结构的编解码 + 反射 |
| `..._TEMPLATE_STRUCT(tparams, name, fields)` | :1047 | 模板结构的定义 + 比较 + 打印 |
| `..._TEMPLATE_STRUCT_SERIALIZE(tparams, name, fields)` | :1053 | 模板结构编解码（带字段名）+ 反射 |
| `..._TEMPLATE_STRUCT_SERIALIZE_NO_FIELD_NAMES(tparams, name, fields)` | :1058 | 同上，不带字段名 |
| `..._TEMPLATE_EMPTY_STRUCT(tparams, name)` | :1064 | 模板空结构 |

关键点：`TM_BASIC_CBOR_CAPABLE_STRUCT` **只给定义、比较和打印**。序列化与反射都在 `_SERIALIZE*` 里，必须另外调一次。两个宏总是成对出现。

打印格式为 `name{field=value field2=value2 }`（注意末尾有空格）；空结构打印为 `name{}`。

### 4. 枚举转字符串家族

```cpp
// tm_basic/tm_kit/basic/SerializationHelperMacros.hpp:1080-1081（源码注释）
// 若希望枚举按底层整数类型序列化，则完全不需要这些宏。
```

四种形状 × 三种序列化严格度，共 12 个顶层宏（:2488–:2534）：

| 形状 | 仅定义+打印 | +序列化 | +严格解码 |
|---|---|---|---|
| 基本 | `..._ENUM_AS_STRING` :2488 | `..._SERIALIZE` :2492 | `..._SERIALIZE_STRICT` :2496 |
| 带别名 | `..._ENUM_AS_STRING_WITH_ALTERNATES` :2500 | :2504 | :2508 |
| 带指定值 | `..._ENUM_AS_STRING_WITH_VALUES` :2512 | :2516 | :2520 |
| 别名+值 | `..._ENUM_AS_STRING_WITH_ALTERNATES_AND_VALUES` :2524 | :2528 | :2532 |

"带别名"允许一个枚举值接受多个输入字符串；"带指定值"允许显式指定底层整数值。`_STRICT` 版本在遇到无法识别的字符串时报错，非 STRICT 版本则回退到默认值——跨进程通信时，宽松解码会把拼错的字段名静默吞掉。

### 5. 内置的 trait 特化（可作为手写特化的范本）

框架自身为 `tm_infra` 的两个版本化类型手写了特化，是学习契约最好的样本：

```cpp
// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:29
template <class V, class D, class Cmp>
class StructFieldInfo<infra::VersionedData<V,D,Cmp>> {
public:
    static constexpr std::string_view REFERENCE_NAME = ...;              // :33
    static constexpr std::array<std::string_view,2> FIELD_NAMES =
        { "version", "data" };                                           // :34
    static constexpr int getFieldIndex(std::string_view const &);         // :37
};
// StructFieldTypeInfo<VersionedData,0> :48，<...,1> :62

// tm_basic/tm_kit/basic/StructFieldInfoHelper.hpp:77
template <...>
class StructFieldInfo<infra::GroupedVersionedData<...>> {
    static constexpr std::array<std::string_view,3> FIELD_NAMES =
        { "groupID", "version", "data" };                                // :82
};
// StructFieldTypeInfo 特化 :99 / :113 / :127
```

注意这两处都**没有**提供 `StructFieldOffsetInfo` 特化。

### 6. StructFieldInfo 全家桶（14 个头文件）

反射之上的泛型能力，按用途分组：

| 头文件 | 行数 | 关键入口 |
|---|---|---|
| `StructFieldInfoHelper.hpp` | 130 | 三个 trait 的主模板 + `HasStructFieldInfo` concept |
| `StructFieldInfoUtils.hpp` | — | `StructFieldInfoBasedInitializer<T>` :27、`StructFieldInfoBasedHash<T>` :66 |
| `StructFieldInfoHelper_Tuple.hpp` | 182 | `StructFieldInfo<std::tuple<Ts...>>` :9，让 tuple 直接具备反射 |
| `StructFieldInfoHelper_NamedField.hpp` | 157 | `NamedItem<Name,T>` :14，给单个值挂上字段名 |
| `ConcatStructFieldInfo.hpp` | 300 | `ConcatStructFields<Ss...>` 的反射 :159，把多个结构拼成一个 |
| `StructFieldFlattenedInfo.hpp` | 193 | `StructFieldFlattenedInfo<T>` :142、`Cursor` :150、`CursorBasedAccess` :156 — 递归展平嵌套结构 |
| `StructFieldInfoBasedCopy.hpp` | 606 | `StructuralCopy` :565（按字段名匹配）、`FlatCopy` :585（按展平顺序） |
| `StructFieldInfoBasedTraverse.hpp` | 443 | 通用遍历，含 6 种容器特化（:63/:97/:131/:165/:199/:233） |
| `StructFieldInfoBasedTuplefy.hpp` | 116 | 结构 ↔ tuple 互转 |
| `StructFieldInfoWithMaskingFilter.hpp` | 601 | `MaskedStruct<T,maskF>` 的反射 :100、`PrintHelper` :157 — 字段级裁剪（脱敏/瘦身） |
| `StructFieldInfoBasedCsvUtils.hpp` | — | CSV 读写，见 [07 章](07-csv-hdf5-flatpack.md) |
| `StructFieldInfoBasedHdf5Utils.hpp` | — | HDF5 落盘，见 07 章 |
| `StructFieldInfoBasedFlatPackUtils.hpp` | — | 定长扁平打包，见 07 章 |
| `StructFieldInfoBasedDynamicView.hpp` | — | 运行期按名访问字段，见 07 章 |

`StructFieldInfoUtils.hpp` 中的 `StructFieldInfoBasedHash<T>` 为常见类型提供了逐个特化：`std::array` :98、`optional` :109、`list` :120、`valarray` :131、`vector` :142、`deque` :153、`set` :164、`map` :175、`unordered_set` :188、`unordered_map` :199、`system_clock::time_point` :211、`TimePointAsString` :218、`std::tm` :225、`ByteData` :242、`ByteDataWithTopic` :249、`ByteDataWithID` :259。不在此列的自定义容器需要自行特化。

## 最小可用示例

### 基本用法：定义 + 序列化（不带字段名）

```cpp
// 来源：tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:32-40
#define TestDataFields \
    ((int32_t, id)) \
    ((std::string, name)) \
    ((double, amount))

TM_BASIC_CBOR_CAPABLE_STRUCT(test_data, TestDataFields);
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES(test_data, TestDataFields);
```

两行宏之后，`test_data` 具备：`operator==`、`operator<`、`operator<<`（打印）、CBOR 编解码，以及 `StructFieldInfo<test_data>`——后者让它可以直接喂给 CSV / HDF5 / 数据库 importer-exporter。

### 带字段名的序列化

```cpp
// 来源：tm_examples/db_one_list_subscription/ReadOnlyDBOneListData.hpp:14-17
TM_BASIC_CBOR_CAPABLE_STRUCT(DBKey, DBKeyFields);
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE(DBKey, DBKeyFields);

TM_BASIC_CBOR_CAPABLE_STRUCT(DBData, DBDataFields);
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE(DBData, DBDataFields);
```

带字段名的 CBOR 是 map 形式（键为字段名字符串），体积更大但容忍字段顺序变化；不带字段名是 array 形式，紧凑但要求收发双方字段顺序完全一致。

### 空结构

```cpp
// 来源：tm_examples/db_one_list_subscription/gui_client/GuiClientDataFlow.hpp:48
TM_BASIC_CBOR_CAPABLE_EMPTY_STRUCT(GuiExitEvent);
```

空结构常用作"信号"类型（退出通知、心跳触发），不携带数据只表达事件发生。

### 模板结构

```cpp
// 来源：tm_examples/bcl_compat_test/CppNoCodeGenShare/CppNoCodeGenStruct.hpp:70-79
TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT(((typename, Env)), QueryNoCodeGen,  QUERY_FIELDS);
TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT(((typename, Env)), ResultNoCodeGen, RESULT_FIELDS);

TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT_SERIALIZE_NO_FIELD_NAMES(
    ((typename, Env)), bcl_compat_test::QueryNoCodeGen,  QUERY_FIELDS);
TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT_SERIALIZE_NO_FIELD_NAMES(
    ((typename, Env)), bcl_compat_test::ResultNoCodeGen, RESULT_FIELDS);
```

注意 `_TEMPLATE_STRUCT` 用的是**不带命名空间**的 `QueryNoCodeGen`（因为宏在 `namespace bcl_compat_test {` 内部调用，见 `:11`），而 `_SERIALIZE` 系列用的是**全限定名** `bcl_compat_test::QueryNoCodeGen`（因为宏展开会跳到 `dev::cd606::tm::basic` 命名空间）。两者写法不一致，是实践中最常见的编译错误来源。

### 字段类型含逗号：两分支写法

字段是 Boost.PP 二元组，`_ITEM_DEF`（:51）用 `BOOST_PP_TUPLE_ELEM(0,elem)` 取类型。因此 `std::array<T, 5>` 这种带顶层逗号的类型会把二元组撕成三元组。框架提供两条互斥的解法，按编译器分支：

```cpp
// 来源：tm_examples/csv_test/CsvTest.cpp:24-49（节选）
#ifdef _MSC_VER
    #define TestDataFields \
        ((std::string, name)) \
        ((int32_t, amount)) \
        ((std::optional<inside_data>, inside)) \
        ((inside_data, inside2)) \
        ((TM_BASIC_CBOR_CAPABLE_STRUCT_PROTECT_TYPE(std::array<inside_data, 5>), moreData)) \
        ((std::tm, theTime)) \
        ((std::chrono::system_clock::time_point, tp))
#else
    #define TestDataFields \
        ((std::string, name)) \
        ((int32_t, amount)) \
        ((std::optional<inside_data>, inside)) \
        ((inside_data, inside2)) \
        (((std::array<inside_data, 5>), moreData)) \
        ((std::tm, theTime)) \
        ((std::chrono::system_clock::time_point, tp))
#endif
```

MSVC 分支用 `PROTECT_TYPE(...)`（变参宏，把逗号吸收进 `__VA_ARGS__`）；其他编译器用**多包一层括号** `(((std::array<inside_data, 5>), moreData))`，让内层括号把逗号困在同一个元组元素里。

机制在 `SerializationHelperMacros.hpp:36-48`：

```cpp
// :35-36
template <typename T> struct macro_type_resolver {};
template <typename T, typename U> struct macro_type_resolver<T(U)> { using type_name = U; };

#ifdef _MSC_VER                                                      // :39
    #define TM_BASIC_CBOR_CAPABLE_STRUCT_PROTECT_TYPE(...) \         // :42
        typename ...::macro_type_resolver<void(__VA_ARGS__)>::type_name
    #define TM_BASIC_CBOR_CAPABLE_STRUCT_TYPE_NAME(x)  x             // :44
#else
    #define TM_BASIC_CBOR_CAPABLE_STRUCT_TYPE_NAME(x) \              // :47
        typename ...::macro_type_resolver<void(x)>::type_name
#endif
```

两条路径殊途同归：都靠函数类型 `void(T)` 的偏特化把类型从括号里"剥"出来。差别在于谁来写这层包装——MSVC 下由 `PROTECT_TYPE` 显式写出，其他编译器下 `TYPE_NAME` 已内建该展开，开发者只需补一层括号使 `void((T))` 仍能匹配 `macro_type_resolver<T(U)>`。

同样的两分支写法也出现在 `tm_examples/bcl_compat_test/CppNoCodeGenShare/CppNoCodeGenStruct.hpp:12-47`，字段类型是带模板参数的 `basic::SingleLayerWrapperWithID<6,std::string>`。

### 反射的直接使用

```cpp
using Info = basic::StructFieldInfo<test_data>;
static_assert(Info::HasGeneratedStructFieldInfo);

constexpr int idx = Info::getFieldIndex("amount");            // 命中返回下标，否则 -1
static_assert(idx >= 0, "字段名拼错了");

using FieldInfo = basic::StructFieldTypeInfo<test_data, idx>;
test_data d;
FieldInfo::access(d) = 3.14;                                   // 写
double v = FieldInfo::constAccess(d);                          // 读

// 遍历所有字段名
for (auto const &n : Info::FIELD_NAMES) { /* ... */ }
```

`getFieldIndex` 是 `constexpr`，可以在 `static_assert` 中校验字段名，把运行期的"字段不存在"错误提前到编译期。

### 结构初始化

```cpp
// tm_basic/tm_kit/basic/StructFieldInfoUtils.hpp:61
test_data d;
basic::struct_field_info_utils::initialize(d);   // 按字段类型逐个置零/置默认
```

`StructFieldInfoBasedInitializer<T>::initialize`（:41）对 `std::tm` 有一处 MSVC 专属处理——把 `tm_mday` 置为 `1`，因为全零的 `std::tm` 在 MSVC 的时间函数里是非法日期。

## 实时 / 回测行为差异

宏与反射全部在编译期完成，**本身不区分实时与回测**。需要注意的是两种模式下的典型搭配：

| 维度 | 实时模式 | 回测模式 |
|---|---|---|
| 字段名模式 | 跨进程通信多用 `NO_FIELD_NAMES`（紧凑，降低网络开销） | 读本地 CSV/HDF5 常用带字段名（容忍列顺序变化） |
| 反射用途 | 主要服务 tm_transport 的序列化与心跳 | 主要服务 CSV / HDF5 / FlatPack 批量读入 |
| `StructFieldOffsetInfo` | 极少直接用 | FlatPack / HDF5 的内存布局映射依赖它 |

## 易错点

**1. 只写 `TM_BASIC_CBOR_CAPABLE_STRUCT` 就以为能序列化**
这是最高频的错误。该宏（:1015）只生成定义、`==`、`<`、打印。CBOR 编解码**和** `StructFieldInfo` 反射都在 `_SERIALIZE` / `_SERIALIZE_NO_FIELD_NAMES` 里（:1021 / :1026）。症状通常是一句很长的模板错误，或 `HasGeneratedStructFieldInfo` 为 `false` 导致 CSV / 传输组件选不到特化。规则：两个宏总是成对写。

**2. `EncDecWithFieldNames` 必须跨进程一致**
`_SERIALIZE` 把 `withFieldName` 置为 `true`（:1024），`_SERIALIZE_NO_FIELD_NAMES` 置为 `false`（:1029），该值写进 `StructFieldInfo::EncDecWithFieldNames`（:912）并决定 CBOR 的物理形态（map 还是 array）。发送端与接收端若选了不同的宏，解码会得到乱数据或直接失败，而编译期毫无提示——因为两边是独立编译单元。升级协议时要同步改双方。

**3. 不带字段名时，字段顺序即协议**
`NO_FIELD_NAMES` 模式下 CBOR 是数组形式，字段顺序就是 wire 格式的一部分。在字段清单中间插入一个新字段，会让所有旧版本进程解析错位。新字段一律追加到清单末尾。

**4. 空结构没有 `StructFieldOffsetInfo`**
`_EMPTY_STRUCT_FIELD_INFO`（:933）只生成 `StructFieldInfo`，其中 `EncDecWithFieldNames` 硬编码为 `false`（:939）、`FIELD_NAMES` 为零长数组（:941）、`getFieldIndex` 恒返回 `-1`（:942）。它**不生成** `StructFieldOffsetInfo`，所以空结构的 `HasGeneratedStructFieldOffsetInfo` 保持 `false`。依赖偏移量的组件（FlatPack 等）对空结构需要单独处理。相比之下 TEMPLATE 版本（`_TEMPLATE_STRUCT_FIELD_INFO` :972）**确实**生成 `StructFieldOffsetInfo`。

**5. 模板结构的 `REFERENCE_NAME` 带尖括号**
`_TEMPLATE_STRUCT_FIELD_INFO`（:972）把 `REFERENCE_NAME` 设为 `#name "<>"`，即形如 `"QueryNoCodeGen<>"`，而非实例化后的 `"QueryNoCodeGen<Env>"`。若代码里用 `REFERENCE_NAME` 做协议标识或表名，模板结构的所有实例会得到同一个名字，必须自行区分。

**6. 含逗号的字段类型不能裸写**
`std::array<T,5>`、`std::map<K,V>`、`SingleLayerWrapperWithID<6,std::string>` 这类类型直接写进字段清单会把 Boost.PP 元组撕开，错误信息指向宏内部，极难定位。正确做法见上文的两分支写法。

**7. `PROTECT_TYPE` 在非 MSVC 编译器上根本不存在**
`TM_BASIC_CBOR_CAPABLE_STRUCT_PROTECT_TYPE` 只有一处定义，在 `SerializationHelperMacros.hpp:42` 的 `_MSC_VER` 分支内。在 GCC / Clang 下它是未定义的函数式宏名，预处理器原样放过，到了 C++ 阶段就是一个未声明的标识符，编译失败。因此跨平台代码里它**必须**写在 `#ifdef _MSC_VER` 分支内——`tm_examples/` 中所有生效的调用点都遵守了这一点。

唯一看起来像反例的是 `tm_examples/serialization_test/SerializationTest.cpp:32` 与 `:42`：它们没有 `#ifdef` 保护，但整段位于 `:28-52` 的 `/* */` 块注释内，是已停用的旧代码，从未参与预处理（该文件在 `serialization_test/meson.build:1-6` 中是正常构建目标，能在 GCC 下编译通过，正是因为这段被注释掉了）。该块注释中还出现了 `TM_BASIC_CBOR_CAPABLE_STRUCT_DEF` 这类单切面宏名与 `StructFieldTypeInfo::fieldPointer()`，均不属于本篇描述的当前接口。**不要以这段注释为范本**；需要保护逗号时，照上文 `CsvTest.cpp` 的两分支写法来写。

**8. `TM_SERIALIZATION_HELPER_COMMA_START_POS` 随 Boost 版本变化**

```cpp
// tm_basic/tm_kit/basic/SerializationHelperMacros.hpp:22-30
#if BOOST_VERSION >= 107500
    #ifdef _MSC_VER
    #define TM_SERIALIZATION_HELPER_COMMA_START_POS 2
    #else
    #define TM_SERIALIZATION_HELPER_COMMA_START_POS 1
    #endif
#else
    #define TM_SERIALIZATION_HELPER_COMMA_START_POS 2
#endif
```

该常量用于把 `BOOST_PP_SEQ_FOR_EACH` 的递归深度 `r` 换算成字段下标（`BOOST_PP_SUB(r, COMMA_START_POS)`，见 :887、:892）。Boost 1.75 改变了 `FOR_EACH` 的起始深度，所以这里要分版本。**升级或降级 Boost 时如果字段下标整体偏移 1，根源就在这里**，症状是 `getFieldIndex` 返回值与 `StructFieldTypeInfo` 的下标不对应。这条与仓库中维护旧 Boost 兼容性的要求直接相关。

**9. 宏必须在全局命名空间调用**
`_SERIALIZE` 系列展开时会写 `namespace dev { namespace cd606 { ... }`（:907、:934），如果在自定义命名空间内调用，会生成 `myns::dev::cd606::...`，特化落不到正确的主模板上。实践中的写法是：结构定义宏可以在自己的命名空间内（配合不带限定的名字），`_SERIALIZE` 系列退回全局命名空间并使用全限定名——见上文模板结构示例。

## 第三方依赖

- **Boost.Preprocessor** — 整个宏族的基础，用到 `BOOST_PP_SEQ_FOR_EACH`、`BOOST_PP_TUPLE_ELEM`、`BOOST_PP_TUPLE_ENUM`、`BOOST_PP_STRINGIZE`、`BOOST_PP_COMMA_IF`、`BOOST_PP_SUB`、`BOOST_PP_SEQ_SIZE`。官方文档：https://www.boost.org/doc/libs/release/libs/preprocessor/doc/index.html
  - SEQ 概念（`((a))((b))((c))` 这种形式）：https://www.boost.org/doc/libs/release/libs/preprocessor/doc/data/sequences.html
  - 注意 `BOOST_PP_LIMIT_SEQ`（默认 256）限制了单个结构的最大字段数。
- **宏参数中的逗号问题** — 两种解法的出处：https://stackoverflow.com/questions/13842468/comma-in-c-c-macro （`SerializationHelperMacros.hpp:40-41` 的源码注释直接引用了该链接）
- **Boost 版本宏** `BOOST_VERSION` — https://www.boost.org/doc/libs/release/libs/config/doc/html/index.html

## 相关章节

- [序列化格式](03-serialization.md) — `ByteData`、CBOR 的具体 wire 格式、ProtoInterop、JSON
- [CSV / HDF5 / FlatPack](07-csv-hdf5-flatpack.md) — 建立在本篇反射契约之上的批量 I/O
- [量化值类型](06-value-types.md) — `FixedPrecisionShortDecimal`、`DateHolder` 等自带反射支持的类型
- [tm_basic 概览](00-overview.md) — 头文件组织
- [时间与数据包装](../tm_infra/07-time-and-data.md) — `VersionedData` / `GroupedVersionedData` 的定义（其反射特化在本篇 `StructFieldInfoHelper.hpp` 中）
