---
title: 序列化格式
library: tm_basic
headers: [tm_kit/basic/ByteData.hpp, tm_kit/basic/ProtoInterop.hpp, tm_kit/basic/NlohmannJsonInterop.hpp]
keywords: [ByteData, ByteDataView, ByteDataWithTopic, ByteDataWithID, CBOR, RunCBORSerializer, RunCBORDeserializer, RunSerializer, RunDeserializer, DirectlySerializableChecker, ProtobufStyleSerializableChecker, ProtoInterop, Proto, ProtoEncoder, ProtoDecoder, ProtoWrappable, IProtoDecoder, Json, JsonEncoder, JsonWrappable, JsonDecoder, read_simd, read_simd_ondemand, RemainingFieldHandler, IsRemainingFieldHandler, JsonFieldMapping, JsonRequiredField, JsonVariant, JsonVariantAutoDetect, JsonVariantTypeMark, JsonVariantAutoDetectTypeMark, simdjson, nlohmann_json, 序列化, protobuf, JSON]
---

# 序列化格式

## 用途

`tm_basic` 的序列化基础设施覆盖三种 wire 格式：CBOR、protobuf wire-format 和 JSON。三者都建立在同一套"字节流传递"抽象之上：

- **CBOR 层**（`ByteData.hpp`）— 低级 tag-length-value 编码，直接对 C++ 类型操作，无需中间表示
- **字符串层**（`ByteData.hpp`）— `RunSerializer<T>` / `RunDeserializer<T>`：统一的序列化调用入口，根据 `T` 的特征分发到 CBOR 或 protobuf-style `SerializeToString` / `ParseFromString`
- **ProtoInterop**（`ProtoInterop.hpp`）— 手写 protobuf wire-format 编解码，不依赖 protoc，通过 `Proto<T>` 包装器接入字符串层
- **NlohmannJsonInterop**（`NlohmannJsonInterop.hpp`）— 基于 nlohmann_json，含 simdjson 快速解码路径，通过 `Json<T>` 包装器接入字符串层

量化程序的典型使用场景：跨进程通信（`tm_transport`）使用字符串层，本地批量存储（CSV/HDF5）使用 CBOR 层，与外部 REST 接口或配置文件交互时使用 JSON 层。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/ByteData.hpp>          // CBOR层 + 字符串层 + 基础字节类型
#include <tm_kit/basic/ProtoInterop.hpp>       // protobuf wire-format
#include <tm_kit/basic/NlohmannJsonInterop.hpp>// nlohmann_json + simdjson

namespace dev::cd606::tm::basic::bytedata_utils    // RunCBORSerializer/Deserializer、RunSerializer/Deserializer、DirectlySerializableChecker
namespace dev::cd606::tm::basic::proto_interop     // ProtoEncoder/Decoder/Wrappable、IProtoDecoder、Proto<T>
namespace dev::cd606::tm::basic::nlohmann_json_interop  // JsonEncoder/Decoder/Wrappable、Json<T>、RemainingFieldHandler
```

## 核心类型与签名

### 1. 基础字节类型（`ByteData.hpp:36-75`）

```cpp
// tm_basic/tm_kit/basic/ByteData.hpp:36
struct ByteData { std::string content; };

// :39 — 不是 "line" 类型，无序列化支持；仅用于打印（不拷贝）
struct ByteDataView { std::string_view content; };

// :48 — 带 topic 的字节流，用于发布/订阅传输
struct ByteDataWithTopic { std::string topic; std::string content; };

// :53 — 带 ID 的字节流（transport 层 ID 已转为字符串）
struct ByteDataWithID { std::string id; std::string content; };

// :66 — 显式 CBOR 包装器；作为 RunSerializer 的入口类型
template <class T>
struct CBOR { using value_type = T; T value; };

// :71 — 带最大尺寸提示的 CBOR；超出 maxSizeHint 则 UB
template <class T>
struct CBORWithMaxSizeHint { T value; std::size_t maxSizeHint; };
```

### 2. CBOR 层：`RunCBORSerializer` / `RunCBORDeserializer`

```cpp
// tm_basic/tm_kit/basic/ByteData.hpp:111
template <class T, typename Enable=void>
struct RunCBORSerializer {
    static std::string apply(T const &data);
    // 不安全的预分配版本，调用方负责 output 足够大
    static std::size_t apply(T const &data, char *output);
    static std::size_t calculateSize(T const &data);
};

template <class T, typename Enable=void>
struct RunCBORDeserializer {
    // 分配版：返回 (值, 消耗字节数)；失败返回 nullopt
    static std::optional<std::tuple<T, size_t>> apply(
        std::string_view const &data, size_t start);
    // 原地版：写入 output，返回消耗字节数；失败返回 nullopt
    static std::optional<size_t> applyInPlace(
        T &output, std::string_view const &data, size_t start);
};
```

已有完整特化的类型：`bool`、`uint8/16/32/64_t`、`int8/16/32/64_t`、`float`、`double`、`std::string`、`ByteData`、`ByteDataWithTopic`、`ByteDataWithID`、`std::vector<A>`、`std::array<A,N>`、`std::list<A>`、`std::deque<A>`、`std::set<A>`、`std::unordered_set<A>`、`std::map<K,V>`、`std::unordered_map<K,V>`、`std::optional<A>`、`std::unique_ptr<A>`、`std::shared_ptr<A>`、`std::shared_ptr<const A>`、`VoidStruct`、`std::monostate`、`ConstType<N>`、`ConstValueType<T,val>`、`ConstStringType<T>`、`SingleLayerWrapperWithID<N,T>`、`SingleLayerWrapperWithTypeMark<Mark,T>`。任何带 `HasGeneratedStructFieldInfo` 的 struct 均由 `SerializationHelperMacros.hpp` 自动生成特化。

### 3. 字符串层：`RunSerializer` / `RunDeserializer`

```cpp
// tm_basic/tm_kit/basic/ByteData.hpp:2819
template <class T, typename Enable=void>
struct RunSerializer {
    static std::string apply(T const &data);
    // 默认实现调用 data.SerializeToString(&s)（protobuf-style）
};

template <class T, typename Enable=void>
struct RunDeserializer {
    static std::optional<T> apply(std::string_view const &data);
    static std::optional<T> apply(std::string const &data);
    static bool applyInPlace(T &output, std::string_view const &data);
    static bool applyInPlace(T &output, std::string const &data);
};
```

`RunSerializer` 的分发优先级：

1. `T = CBOR<U>` → `RunCBORSerializer<U>::apply()`（`:2839`）
2. `T = CBORWithMaxSizeHint<U>` → 预分配缓冲区后调用 CBOR 序列化（`:2845`）
3. `T = std::string` / `ByteData` → 直接返回内容（`:2861`，`:2867`）
4. `T = SingleLayerWrapperWithID<N,std::string>` 等 → 透传内部字符串（`:2879`）
5. 其他 → 调用 `T::SerializeToString(&s)`（前提：`DirectlySerializableChecker<T>::IsDirectlySerializable()`）

`RunDeserializer` 对称：`CBOR<T>` 走 CBOR 解码，`std::string`/`ByteData` 直接拷贝，其他类型走 `T::ParseFromString()`。

`NlohmannJsonInterop.hpp` 在 `:4227` 和 `:4235` 处为 `Json<T>` 注册了 `RunSerializer` / `RunDeserializer` 特化，使 JSON 格式透明接入字符串层。

#### `DirectlySerializableChecker<T>`（`:2686`）

检查 `T` 是否具有 `SerializeToString(std::string *)` 和 `ParseFromString(std::string_view const &)`（或 `std::string const &`）成员。`Proto<T>` 和 `Json<T>` 均满足此检查，因此可直接作为 `RunSerializer` 的 `T` 类型参数使用。内置特化有 `CBOR<T>`、`CBORWithMaxSizeHint<T>`、`std::string`、`ByteData`、`std::array<char,N>`、`std::shared_ptr<const T>`（`:2793–2816`）。

### 4. ProtoInterop：protobuf wire-format 互操作

头文件 `ProtoInterop.hpp` 实现了一套手写的 protobuf wire-format 编解码，无需 protoc，完全基于模板特化。

#### 4.1 命名空间与类型别名（`:1-50`）

```cpp
// tm_basic/tm_kit/basic/ProtoInterop.hpp
namespace dev::cd606::tm::basic::proto_interop {

// ZigZag / Fixed 编码标记
using Int32   = int32_t;
using Int64   = int64_t;
using UInt32  = uint32_t;
using UInt64  = uint64_t;
using SInt32  = SingleLayerWrapperWithTypeMark<ZigZag, int32_t>;   // varint + zigzag
using SInt64  = SingleLayerWrapperWithTypeMark<ZigZag, int64_t>;
using Fixed32 = SingleLayerWrapperWithTypeMark<Fixed,  uint32_t>;  // fixed-width 4B
using Fixed64 = SingleLayerWrapperWithTypeMark<Fixed,  uint64_t>;  // fixed-width 8B
// SFixed32/SFixed64 → 带符号的 Fixed32/Fixed64
using SFixed32 = SingleLayerWrapperWithTypeMark<Fixed,  int32_t>;
using SFixed64 = SingleLayerWrapperWithTypeMark<Fixed,  int64_t>;
```

#### 4.2 `ProtoWrappable<T>`（`:215`）

```cpp
template <class T, typename Enable=void>
struct ProtoWrappable { static constexpr bool value = false; };
```

已特化为 `true` 的类型：`bool`、所有整数类型、`float`/`double`、`std::string`、`ByteData`、`std::array<char,N>`、`std::vector<A>`、`std::optional<A>`、`std::unique_ptr<A>`、`std::shared_ptr<A>`、`std::shared_ptr<const A>`、所有 `StructFieldInfo` 结构体（所有字段均满足 `ProtoWrappable`）、ZigZag/Fixed 类型别名、`ConvertibleWithString<T>` 类型、`EncodableThroughProxy<T>`、`EncodableThroughMultipleProxies<T>`（`:3882`）。

结构体的 `ProtoWrappable` 是递归定义（`:1543`）——当且仅当所有字段都满足 `ProtoWrappable<F>::value` 时，结构体才满足。

#### 4.3 `ProtoEncoder<T>` / `ProtoDecoder<T>`（`:221`，`:1630`）

```cpp
// 每个 ProtoEncoder 特化提供
template <class T>
class ProtoEncoder<T, Enable> {
public:
    static constexpr uint64_t thisFieldNumber(uint64_t inputFieldNumber);
    static constexpr uint64_t nextFieldNumber(uint64_t inputFieldNumber);
    static void write(std::optional<uint64_t> fieldNumber, T const &data,
                      std::ostream &os, bool writeDefaultValue);
};

// 每个 ProtoDecoder 特化
template <class T>
class ProtoDecoder<T, Enable> : public IProtoDecoder<T> {
public:
    ProtoDecoder(T *output, uint64_t baseFieldNumber);
    static std::vector<uint64_t> responsibleForFieldNumbers(uint64_t baseFieldNumber);
};
```

`fieldNumber = std::nullopt` 表示"不写字段头"，用于顶层结构体（字段序号由结构的 `StructFieldInfo` 中字段顺序决定，起始从 1 递增，每个字段消耗的字段号数量取决于其编码类型）。

#### 4.4 `IProtoDecoder<T>`（`:1616`）

```cpp
class IProtoDecoderBase {
public:
    virtual std::optional<std::size_t> handle(
        internal::FieldHeader const &fh,
        std::string_view const &input,
        std::size_t start) = 0;
    std::optional<std::size_t> handleWithOuterHeader(
        std::string_view const &input, std::size_t start);
};

template <class T>
class IProtoDecoder : public IProtoDecoderBase {
public:
    IProtoDecoder(T *output);
protected:
    virtual std::optional<std::size_t> read(
        T &output,
        internal::FieldHeader const &fh,
        std::string_view const &input,
        std::size_t start) = 0;
};
```

`handleWithOuterHeader` 先读字段头再调 `handle`，适用于包装在外层 length-delimited 中的非结构体类型。

#### 4.5 `Proto<T>` 包装器（`:3427`）

```cpp
// tm_basic/tm_kit/basic/ProtoInterop.hpp:3427
template <class T, typename Enable = std::enable_if_t<ProtoWrappable<T>::value>>
class Proto {
public:
    Proto();
    Proto(T const &t);
    Proto(T &&t);

    void SerializeToStream(std::ostream &os) const;
    void SerializeToString(std::string *s) const;
    bool ParseFromStringView(std::string_view const &s);
    bool ParseFromString(std::string const &s);

    // 静态便捷方法
    static void runSerialize(T const &t, std::ostream &os);      // :3518
    static bool runDeserialize(T &t, std::string_view const &input); // :3525
    static std::string runSerializeIntoValue(T const &t);        // :3539

    T const &value() const;
    T &value();
    T &operator*();
    T const &operator*() const;
    T *operator->();
    T const *operator->() const;
};
```

`Proto<T*>` 和 `Proto<T const *>` 变体（`:3546`，`:3625`）通过指针持有数据，避免拷贝，适用于性能敏感路径。

### 5. NlohmannJsonInterop：JSON + simdjson

#### 5.1 `JsonWrappable<T>` 与 `JsonEncoder<T>`（`:58–134`）

```cpp
// tm_basic/tm_kit/basic/NlohmannJsonInterop.hpp:58
template <class T, typename Enable=void>
class JsonEncoder {};     // 空主模板

template <class T, typename Enable=void>
struct JsonWrappable { static constexpr bool value = false; };
```

`JsonEncoder<T>` 已有特化的类型：所有整数类型（`:66`）、浮点数（`:88`）、`bool`（`:108`）、`enum`（`:124`）、`enum with string representation`（通过 `ConvertibleWithString`）、`std::string`、`ByteData`、`std::vector`、`std::optional`、`std::map`、`std::unordered_map`、以及所有有 `StructFieldInfo` 反射的结构体。

每个 `JsonEncoder` 特化的接口：

```cpp
template <class T>
class JsonEncoder<T, ...> {
    static void write(nlohmann::json &output,
                      std::optional<std::string> const &key,
                      T const &data);
    // key = nullopt 时写 output 本身；key = "fieldName" 时写 output[fieldName]
};
```

#### 5.2 `RemainingFieldHandler<T>`（`:44`）

它不是手写结构体，而是由 `TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT` 宏生成的（字段定义在 `:36`–`:41` 的 `REMAINING_FIELD_HANDLER_FIELDS`）：

```cpp
// tm_basic/tm_kit/basic/NlohmannJsonInterop.hpp:36-44（宏展开后的等价形态）
template <class T>
struct RemainingFieldHandler {
    std::map<std::string, T> data;   // ← 成员名是 data，不是 remainingFields
};

// trait（:47、:52）
template <class T> class IsRemainingFieldHandler { static constexpr bool value = false; };
template <class T> class IsRemainingFieldHandler<RemainingFieldHandler<T>> {
    static constexpr bool value = true;
    using UnderlyingType = T;
};
```

在结构体 JSON 解码时，若某字段在 `StructFieldInfo::FIELD_NAMES` 中找不到，会被收进这个 `data` map。用于**兼容将来新增的字段而不丢弃已有数据**（前向兼容的 JSON 读取）。

#### 5.2.1 其余 JSON 专用类型（`:520`–`:545`、`:776`）

| 类型 | 位置 | 作用 |
|---|---|---|
| `JsonRequiredFieldMark` / `JsonRequiredField<T>` / `IsJsonRequiredField<T>` | `:531` / `:533` / `:535` | 把字段包一层声明"解码时必须存在"；是 `SingleLayerWrapperWithTypeMark` 的别名，编码时透明透传 |
| `JsonVariantTypeMark` / `JsonVariant<Ts...>` | `:538` / `:541` | `SingleLayerWrapperWithTypeMark<JsonVariantTypeMark, std::variant<std::monostate,Ts...>>`——**带类型标签的 JSON 变体**，编码成外部系统常见的 `{"type":..., "value":...}` 形式 |
| `JsonVariantAutoDetectTypeMark` / `JsonVariantAutoDetect<Ts...>` | `:539` / `:543` | 同上，但解码时**按结构自动判别**该落到哪个分支，不需要外部提供 type 标签 |
| `JsonFieldMapping` | `:776` | 见下 |

`JsonFieldMapping` 是**C++ 字段名 → JSON 键名**的映射表：

```cpp
// tm_basic/tm_kit/basic/NlohmannJsonInterop.hpp:776
using JsonFieldMapping = std::unordered_map<
    std::type_index, std::unordered_map<std::string, std::string>
>;
// 外层 key 是结构体类型，内层 key 是 C++ 字段名，value 是 JSON 里的键名
```

它作为**可选末位参数**贯穿整套 JSON 编解码接口（`fillFieldNameMapping`、`read`、`read_simd`、`read_simd_ondemand` 都收它，见 `:789`、`:790`、`:810`、`:860`）。用途：对接外部 JSON API 时，C++ 侧写 `myField`、JSON 侧要 `my_field` 或 `MyField`，不必改结构体字段名。

`JsonEncoder<SingleLayerWrapperWithTypeMark<M,T>>` 对**除上面两个 Variant 标记之外**的所有 TypeMark 都透明透传（`:546`、`:553` 的 `enable_if` 排除了 `JsonVariantTypeMark` 与 `JsonVariantAutoDetectTypeMark`）——所以 `JsonRequiredField<T>` 与其它标记包装不会在 wire 上产生额外层级。

#### 5.3 `JsonDecoder<T>` 与 `read_simd`

`JsonDecoder<T>` 有两条解码路径：

1. **nlohmann 路径**：调用 `nlohmann::json::parse()`，适合通用场景
2. **simdjson 路径**（`read_simd` 系列，`:810`、`:940`、`:1047` 等）：
   - 对实现了 `StructFieldInfo` 的结构体提供高性能解码
   - `read_simd` 接受 `simdjson::dom::element` 或 `simdjson::dom::object`
   - `read_simd_ondemand` 模板方法接受 `X &input`，用于 simdjson 的 on-demand 解析模式
   - **simdjson 无独立头文件**，包含 `NlohmannJsonInterop.hpp:28` 的 `#include <simdjson.h>` 即引入

#### 5.4 `Json<T>` 包装器

`Json<T>` 作为 `RunSerializer`/`RunDeserializer`/`DirectlySerializableChecker` 的钩子在 `NlohmannJsonInterop.hpp:4227–4258` 注册，提供：

```cpp
// 注册于 NlohmannJsonInterop.hpp:4227
struct RunSerializer<nlohmann_json_interop::Json<T>> {
    static std::string apply(Json<T> const &data);
    // 内部调用 Json<T>::runSerialize(*data, oss)
};
struct RunDeserializer<nlohmann_json_interop::Json<T>> {
    static std::optional<Json<T>> apply(std::string_view const &data);
    static bool applyInPlace(Json<T> &output, std::string_view const &data);
};
struct DirectlySerializableChecker<nlohmann_json_interop::Json<T>> {
    static constexpr bool IsDirectlySerializable() { return true; }
};
```

此外，`NlohmannJsonInterop.hpp:4263` 还为 `nlohmann::json` 类型本身注册了 `RunCBORSerializer`/`RunCBORDeserializer`，以 `nlohmann::json::to_cbor()` / `from_cbor()` 实现，可在 `CBOR<nlohmann::json>` 场景中使用。

## 最小可用示例

### CBOR 序列化

```cpp
// 来源：tm_examples/db_one_list_subscription/DBTableImporterExporterTest.cpp:51-60（已简化）
// 前提：test_data 已用 TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE 定义
using namespace dev::cd606::tm::basic::bytedata_utils;

test_data d {1, "hello", 3.14};

// 编码
std::string encoded = RunCBORSerializer<test_data>::apply(d);

// 解码（分配版）
auto result = RunCBORDeserializer<test_data>::apply(encoded, 0);
if (result) {
    test_data recovered = std::get<0>(*result);
}

// 解码（原地版，避免拷贝）
test_data out;
auto consumed = RunCBORDeserializer<test_data>::applyInPlace(out, encoded, 0);
```

### Proto 序列化（手写 protobuf wire-format）

```cpp
// 来源：tm_examples/bcl_compat_test 相关文件（已简化）
#include <tm_kit/basic/ProtoInterop.hpp>
using namespace dev::cd606::tm::basic::proto_interop;

// 前提：QueryNoCodeGen<Env> 已用 TM_BASIC_CBOR_CAPABLE_TEMPLATE_STRUCT_SERIALIZE 定义
// 且所有字段均满足 ProtoWrappable

QueryNoCodeGen<TheEnvironment> q;
q.name = "test";
q.amount = 100;

// 序列化
std::string serialized = Proto<QueryNoCodeGen<TheEnvironment>>::runSerializeIntoValue(q);

// 反序列化
QueryNoCodeGen<TheEnvironment> q2;
bool ok = Proto<QueryNoCodeGen<TheEnvironment>>::runDeserialize(q2, serialized);

// 也可用包装器对象
Proto<QueryNoCodeGen<TheEnvironment>> wrapper(q);
std::string s;
wrapper.SerializeToString(&s);
bool ok2 = wrapper.ParseFromString(s);
```

### JSON 序列化

```cpp
// 来源：tm_examples 中涉及 REST 接口的示例（已简化）
#include <tm_kit/basic/NlohmannJsonInterop.hpp>
using namespace dev::cd606::tm::basic::nlohmann_json_interop;

// 前提：MyData 已用 TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE 定义
MyData d {"hello", 42};

// 序列化
std::string json_str = RunSerializer<Json<MyData>>::apply(Json<MyData> {d});

// 反序列化
auto r = RunDeserializer<Json<MyData>>::apply(std::string_view{json_str});
if (r) {
    MyData recovered = r->value();
}
```

### 在 tm_transport 中接入字符串层

`tm_transport` 中的发布/订阅和 facility 调用使用 `RunSerializer<T>` / `RunDeserializer<T>` 接口。选择序列化格式只需改变 `T` 的包装类型：

| 包装类型 | 格式 |
|---|---|
| `T`（有 `_SERIALIZE` 宏） | CBOR |
| `CBOR<T>` | CBOR（显式） |
| `Proto<T>` | protobuf wire-format |
| `Json<T>` | JSON（nlohmann） |

## 实时 / 回测行为差异

序列化本身无实时/回测区分，但在以下方面需注意：

| 维度 | 实时模式 | 回测模式 |
|---|---|---|
| 性能开销 | Proto/CBOR 均适合高频消息 | 通常以吞吐量为主，格式选择影响不大 |
| 日志与调试 | JSON 格式便于人工读取，但体积大 | 单机文件 I/O 中 CBOR 更紧凑 |
| `ByteDataWithTopic` | transport 层发布订阅的 wire 类型 | 回测 CSV/HDF5 通常直接操作结构体，不经 ByteDataWithTopic |

## 易错点

**1. `ByteDataView` 没有序列化支持**  
`ByteDataView`（`:39`）源码注释明确写道："not intended to be a 'line' data type therefore the serialization code is not provided"。它只有 `ProtoEncoder` 特化（仅写，不能读），没有 `RunCBORSerializer`/`RunCBORDeserializer`。发现编译错误 "no matching function for call to `RunCBORSerializer<ByteDataView>`" 时，换用 `ByteData`。

**2. proto 字段号由字段顺序决定，不是名称**  
`ProtoEncoder` 对结构体的编码从字段号 1 开始，按 `StructFieldInfo::FIELD_NAMES` 的顺序递增。若在字段清单中间插入新字段，会改变后续所有字段的字段号，破坏与旧版本的互操作。新字段一律追加到末尾，与 protoc 生成的代码规范一致。

**3. 默认值字段不写入（`writeDefaultValue=false`）**  
`ProtoEncoder::write` 以 `writeDefaultValue=false` 调用时，零值/空值字段不写入 wire，这与标准 protobuf proto3 行为一致。解码端对缺失字段的处理：`optional<T>` 保持 `nullopt`，基本类型保持原始值（初始为零）。若有"必须存在"语义的字段，需要在应用层校验。

**4. `Proto<T>` 要求 `T` 满足 `ProtoWrappable<T>::value == true`**  
如果结构体中有不支持 proto 的字段类型（如 `std::unordered_map`），则整个结构体的 `ProtoWrappable` 为 `false`，`Proto<T>` 无法实例化，报错在 `enable_if` 处，信息不直观。检查方法：`static_assert(proto_interop::ProtoWrappable<MyStruct>::value)`。

**5. simdjson 无独立头文件**  
`simdjson` 通过 `NlohmannJsonInterop.hpp:28` 的 `#include <simdjson.h>` 引入。不要尝试单独 `#include <simdjson.h>` 后使用框架的 `read_simd`，因为后者的特化在 `NlohmannJsonInterop.hpp` 中定义。Windows 下 vcpkg 的 simdjson 需要额外链接 `simdjson.cpp`，见 `tm_basic/README.md:39`。

**6. `RunSerializer` 的默认实现在 GCC 下会 UB**  
`ByteData.hpp:2820-2830` 的默认 `RunSerializer<T>` 在非 MSVC 下直接调用 `data.SerializeToString(&s)` 而不检查 `DirectlySerializableChecker`。若 `T` 没有该方法，链接报错（MSVC 下有 `if constexpr` 守卫）。实际上只有 `Proto<T>` 或 `Json<T>` 等包装类型才满足该接口；不要对裸的自定义结构体使用 `RunSerializer<T>`（不带 `CBOR<>`/`Proto<>`/`Json<>` 包装），要先确认该结构体的 `DirectlySerializableChecker::IsDirectlySerializable()` 为 `true`。

## 第三方依赖

- **nlohmann_json** — `NlohmannJsonInterop.hpp` JSON 编解码的主路径。官方文档：https://github.com/nlohmann/json；API 参考：https://json.nlohmann.me/
- **simdjson** — `NlohmannJsonInterop.hpp` 中的快速 JSON 解码路径（`read_simd`/`read_simd_ondemand`）。官方文档：https://simdjson.org/；API 参考：https://github.com/simdjson/simdjson/blob/master/doc/basics.md。注意：无独立框架头文件，直接由 `NlohmannJsonInterop.hpp:28` 引入。
- **Boost.Endian** — `ByteData.hpp:31` 引入，`RunCBORSerializer`/`ProtoDecoder` 中的大小端转换。官方文档：https://www.boost.org/doc/libs/release/libs/endian/doc/html/endian.html
- **Boost.Hana** — `ByteData.hpp:32` 引入，`DirectlySerializableChecker` 和 `ProtobufStyleSerializableChecker` 中用于在 `constexpr` 上下文检测成员函数存在性。官方文档：https://www.boost.org/doc/libs/release/libs/hana/doc/html/index.html

## 相关章节

- [序列化宏与结构反射](02-struct-field-info.md) — `StructFieldInfo<T>` 契约；`TM_BASIC_CBOR_CAPABLE_*` 宏族
- [CSV / HDF5 / FlatPack](07-csv-hdf5-flatpack.md) — 建立在 `RunCBORSerializer` 之上的批量 I/O
- [日志组件](04-logging.md) — 与序列化无直接关系，但同样依赖 `ByteData` 传递日志信息
- [共享链](08-shared-chain.md) — 链上存储的 value 通常经由 `RunSerializer`/`RunDeserializer` 编解码
- [transport 概览](../tm_transport/00-overview.md) — `RunSerializer<T>` 是 transport 层的序列化入口
