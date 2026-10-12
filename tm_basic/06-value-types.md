---
title: 量化值类型
library: tm_basic
headers: [tm_kit/basic/FixedPrecisionShortDecimal.hpp, tm_kit/basic/DateHolder.hpp, tm_kit/basic/ConstType.hpp, tm_kit/basic/ConstValueType.hpp, tm_kit/basic/ConstStringType.hpp, tm_kit/basic/VoidStruct.hpp, tm_kit/basic/SingleLayerWrapper.hpp]
keywords: [FixedPrecisionShortDecimal, DateHolder, ConstType, ConstValueType, ConstStringType, VoidStruct, SingleLayerWrapper, SingleLayerWrapperWithID, SingleLayerWrapperWithTypeMark, IsFixedPrecisionShortDecimal, ConvertibleWithString, EncodableThroughMultipleProxies, 定点小数, 固定精度, 日期, 交易日, 常量类型, 信号类型, 包装器]
---

# 量化值类型

## 用途

本章覆盖 `tm_basic` 中几类与量化交易场景紧密相关的值类型：

- **`FixedPrecisionShortDecimal<Precision, Underlying>`** — 定点小数，用于价格和数量的无浮点误差表示
- **`DateHolder`** — 轻量日期（年/月/日），用于交易日标识
- **`ConstType<N>`** / **`ConstValueType<T,val>`** / **`ConstStringType`** — 编译期常量标记类型，常用于信道/tag 区分
- **`VoidStruct`** — 空信号类型，代替 `std::monostate` 的可读型
- **`SingleLayerWrapper`** 族 — 泛型包装器，用于区分同类型在同一 variant 中的不同语义角色

## 头文件与命名空间

```cpp
#include <tm_kit/basic/FixedPrecisionShortDecimal.hpp>
#include <tm_kit/basic/DateHolder.hpp>
#include <tm_kit/basic/ConstType.hpp>
#include <tm_kit/basic/ConstValueType.hpp>
#include <tm_kit/basic/ConstStringType.hpp>
#include <tm_kit/basic/VoidStruct.hpp>
#include <tm_kit/basic/SingleLayerWrapper.hpp>

namespace dev::cd606::tm::basic   // 所有类型均在此命名空间
```

## 核心类型与签名

### 1. `FixedPrecisionShortDecimal<Precision, Underlying>`（`:26`）

```cpp
// tm_basic/tm_kit/basic/FixedPrecisionShortDecimal.hpp:26
template <std::size_t Precision, typename Underlying = int64_t>
class FixedPrecisionShortDecimal {
public:
    using UnderlyingType = Underlying;
    static constexpr std::size_t PrecisionValue = Precision;

    // 构造：零值（默认）、底层整数（显式）、double（显式，四舍五入）、字符串（解析）
    FixedPrecisionShortDecimal();
    explicit FixedPrecisionShortDecimal(Underlying u);
    explicit FixedPrecisionShortDecimal(double d);
    explicit FixedPrecisionShortDecimal(std::string_view const &s);

    // 从整数值（不带精度换算）构造，等价于 val * 10^Precision
    template <class T> static FixedPrecisionShortDecimal fromIntegral(T u);  // :169

    // 从另一精度/底层类型转换（带四舍五入）
    template <std::size_t NewPrecision, typename NewUnderlying = Underlying>
    FixedPrecisionShortDecimal<NewPrecision, NewUnderlying> changePrecision() const; // :174

    // 跨精度/底层类型的显式转换运算符
    template <std::size_t AnotherPrecision, typename AnotherUnderlying>
    explicit operator FixedPrecisionShortDecimal<AnotherPrecision, AnotherUnderlying>() const; // :226

    // 从（精度，整数值）对构造（运行期精度）
    template <class I> static FixedPrecisionShortDecimal fromPrecisionAndValue(
        std::size_t inputPrecision, I inputValue); // :231

    // 边界值
    static constexpr FixedPrecisionShortDecimal zero();  // :254
    static constexpr FixedPrecisionShortDecimal max();   // :257
    static constexpr FixedPrecisionShortDecimal min();   // :260

    // 比较（底层整数直接比较）
    bool operator==(FixedPrecisionShortDecimal const &) const;
    bool operator<(FixedPrecisionShortDecimal const &) const;
    // >, >=, <=, != 均提供

    FixedPrecisionShortDecimal abs() const;             // :283
    FixedPrecisionShortDecimal operator-() const;       // :291（Underlying 为无符号时抛出）
    FixedPrecisionShortDecimal operator+(FixedPrecisionShortDecimal const &) const; // :299
    FixedPrecisionShortDecimal operator-(FixedPrecisionShortDecimal const &) const; // :302
    FixedPrecisionShortDecimal &operator+=(FixedPrecisionShortDecimal const &);     // :305
    FixedPrecisionShortDecimal &operator-=(FixedPrecisionShortDecimal const &);     // :309

    Underlying value() const;                  // :314 — 返回底层整数（实际值 * 10^Precision）
    explicit operator double() const;          // :317
    explicit operator float() const;           // :320
    std::string asString() const;              // :323 — 去尾零的十进制字符串
    explicit operator std::string() const;     // :350
};
```

**序列化互操作**（`:377`）：`FixedPrecisionShortDecimal` 通过 `EncodableThroughMultipleProxies` 支持三种格式：
- **CBOR**：编码为 `tuple<size_t, Underlying>`（精度 + 底层值），可完美往返
- **JSON**：编码为字符串（`asString()`），可与人类可读表示互通
- **Proto**：编码为 `double`，有精度损失，仅用于与外部 proto 接口兼容

`ConvertibleWithString<FixedPrecisionShortDecimal<P,U>>` 已特化（`:356`），因此该类型在所有依赖 `ConvertibleWithString` 的场合（如枚举字段读写、DynamicView、CSV）均可透明使用。

检测工具类：

```cpp
// :21 / :368 — 编译期检测是否为该类型
template <class T>
class IsFixedPrecisionShortDecimal {
public:
    static constexpr bool value = false;
};
// 特化后提供：
//   TheType — 等于 FixedPrecisionShortDecimal<Precision, Underlying>
//   constexpr std::size_t precision
//   UnderlyingType
```

### 2. `DateHolder`（`DateHolder.hpp:12`）

```cpp
// tm_basic/tm_kit/basic/DateHolder.hpp:12
struct DateHolder {
    uint16_t year;
    uint8_t  month;
    uint8_t  day;
};
```

提供的运算符：`==`、`!=`、`<`、`>`、`<=`、`>=`、`operator<<`（打印为 `YYYY-MM-DD`）。

工厂函数与转换（头文件内联实现）：

```cpp
// :60 — 从 time_point 取本地日期
DateHolder dateHolderFromTimePoint(std::chrono::system_clock::time_point const &tp);
DateHolder dateHolderFromTimePoint_Local(std::chrono::system_clock::time_point const &tp); // :69（同上）
DateHolder dateHolderFromTimePoint_Utc(std::chrono::system_clock::time_point const &tp);   // :72
// :81 — 带时区的版本（链接时需要 DateHolder.cpp，依赖 date/tz 库）
DateHolder dateHolderFromZonedTimePoint(std::chrono::system_clock::time_point const &tp,
                                         std::string_view const &timeZoneName);

// :89 — YYYYMMDD 整数互转
DateHolder dateHolderFromYYYYMMDD(int yyyymmdd);
int        dateHolderToYYYYMMDD(DateHolder const &d);

// :99 — 字符串解析（支持 "YYYYMMDD" 和 "YYYY-MM-DD"）
DateHolder parseDateHolder(std::string const &s);

// :85 — 运算（链接时需要 DateHolder.cpp）
int        operator-(DateHolder const &d1, DateHolder const &d2); // 差值（日历天数）
DateHolder operator+(DateHolder const &d, int offset);
DateHolder operator-(DateHolder const &d, int offset);

// :116 — 年份加减（2月29日自动处理）
DateHolder oneYearAgo(DateHolder const &d);
DateHolder oneYearLater(DateHolder const &d);
```

`std::hash<DateHolder>`、`std::equal_to<DateHolder>`、`std::less<DateHolder>` 均已特化（`:132–158`），可直接用于 `unordered_map`/`unordered_set`。

`DateHolder` 本身没有自动生成的序列化宏，因为它没有字段名反射（没有调用 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE`）。需要序列化时，通常将它转为 `int`（`dateHolderToYYYYMMDD`）或 `std::string`，或将 `DateHolder` 作为结构体的 `int` 字段并手写转换。在 `StructFieldInfoBasedHash` 中它已经有特化（见 02 章），可作为 map 的 key。

### 3. `ConstType<N>` / `ConstValueType<T,val>` / `ConstStringType`

```cpp
// tm_basic/tm_kit/basic/ConstType.hpp:8
template <int32_t N>
struct ConstType {};
// 提供：operator==（恒 true）、operator<（恒 false）、std::hash（返回 0）

// tm_basic/tm_kit/basic/ConstValueType.hpp:5
template <typename T, T val>
class ConstValueType {
public:
    using TheType = T;
    static constexpr T TheValue = val;
    constexpr operator T() const { return val; }  // :10
};
// 提供：operator==（恒 true）、operator<（恒 false）

// tm_basic/tm_kit/basic/ConstStringType.hpp:46
// C++20 及以上（带 non-type template parameter 的字符串字面量）：
//   TM_BASIC_CONST_STRING_TYPE("hello") 展开为 ConstStringType<ConstStringType_LiteralWrapper<"hello">>
// C++17（依赖用户自定义字面量或 Boost.PP 展开）：
//   TM_BASIC_CONST_STRING_TYPE("hello") 同样可用，底层实现不同
// 所有版本均提供：static constexpr std::string_view VALUE = ...；operator==（恒 true）；operator<（恒 false）
```

`IsConstStringType<T>` trait（`:133`）可用于检测。

三者的共同用途：作为 `std::variant` 中区分同类型信道的"tag"，或作为 `BasicWithTimeApp` 中无需实际数据的"脉冲"类型。它们在 CBOR 序列化中有完整特化（见 `ByteData.hpp` 中的 `ConstType`/`ConstValueType`/`ConstStringType` 特化）。

### 4. `VoidStruct`（`VoidStruct.hpp:8`）

```cpp
// tm_basic/tm_kit/basic/VoidStruct.hpp:8
struct VoidStruct {};
// 提供：operator==（恒 true）、operator<<（打印 "VoidStruct{}"）
// std::hash、equal_to、less 均已特化（:19-41）
```

`VoidStruct` 与 `std::monostate` 功能相同，但有可读的打印表示，是框架惯用的"空信号"类型，常见于：
- 退出通知（`GuiExitEvent` 等）
- 回调触发型 facility 的返回值
- `bunchWith`/`simpleFinalizer` 的输出类型（无需内容只需触发）

### 5. `SingleLayerWrapper` 族（`SingleLayerWrapper.hpp`）

```cpp
// tm_basic/tm_kit/basic/SingleLayerWrapper.hpp:9
// 简单包装器，无 ID 区分，用于需要强类型包装的场景
template <class T>
struct SingleLayerWrapper {
    using value_type = T;
    T value;
};
// 提供：operator==、operator<

// :22 — 带整数 ID 的包装器，同一底层类型的不同语义角色
template <int32_t N, class T>
struct SingleLayerWrapperWithID {
    using value_type = T;
    T value;
    // 隐式转换：operator T()（:42）
    T       &operator*();       // :45
    T const &operator*() const; // :48
    T       *operator->();      // :51
    T const *operator->() const;// :54
};
// 提供：operator==、operator<

// :67 — 带类型标记的包装器（类型安全区分，无运行期 ID）
template <class Mark, class T>
struct SingleLayerWrapperWithTypeMark {
    using value_type = T;
    T value;
    // 同样提供隐式转换、*, -> 运算符
};
// 提供：operator==、operator<
```

检测 trait（`:112–155`）：
```cpp
IsSingleLayerWrapperWithID<T>::Value        // bool，T 是否为 SingleLayerWrapperWithID
IsSingleLayerWrapperWithID<T>::ID           // int32_t，包装器的 N
IsSingleLayerWrapperWithID<T>::UnderlyingType // 内层类型

IsSingleLayerWrapperWithGivenID<GivenID,T>::Value // T 的 ID 是否等于 GivenID

IsSingleLayerWrapperWithTypeMark<T>::Value  // bool
IsSingleLayerWrapperWithTypeMark<T>::MarkType
IsSingleLayerWrapperWithTypeMark<T>::UnderlyingType
```

在序列化层（`ByteData.hpp`），`SingleLayerWrapperWithID<N,T>` 和 `SingleLayerWrapperWithTypeMark<Mark,T>` 均有 `RunCBORSerializer` 特化，直接透传内层值的 CBOR 编码（外层不附加任何字段）。

## 最小可用示例

### 定点小数：价格与数量（来自 FixedPrecisionDecimalTest.cpp）

```cpp
// 来源：tm_examples/serialization_test/FixedPrecisionDecimalTest.cpp:7-44
#include <tm_kit/basic/FixedPrecisionShortDecimal.hpp>
#include <tm_kit/basic/NlohmannJsonInterop.hpp>
#include <tm_kit/basic/ProtoInterop.hpp>
using D = basic::FixedPrecisionShortDecimal<6>;

// 从字符串构造（支持科学计数法，自动四舍五入到 6 位小数）
D price {"-12345678.55001045E5"};   // 内部底层整数
std::cout << price.asString() << '\n';   // "-1234567855001.04"
std::cout << (double) price << '\n';      // 近似 double

// 在宏定义的结构体中使用（字段 d 类型为 D）
TM_BASIC_CBOR_CAPABLE_STRUCT(Test, ((std::string, a))((D, d))((bool, x)));
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES(Test, ((std::string, a))((D, d))((bool, x)));

Test t {"abc", price, true};
// CBOR 编码：D 字段序列化为 [6, <underlying int64>]
auto enc = basic::bytedata_utils::RunCBORSerializer<Test>::apply(t);
// 也可序列化为 JSON 字符串形式
basic::nlohmann_json_interop::Json<Test>(t).writeToString(&enc);

// 精度转换：6 位精度转 2 位精度（银行家场景）
D p6 {1.23456};
auto p2 = p6.changePrecision<2>();  // 四舍五入 → 1.23
```

### 日期操作（交易日计算）

```cpp
// 来源：DateHolder.hpp 工厂函数（已简化）
#include <tm_kit/basic/DateHolder.hpp>
using namespace dev::cd606::tm::basic;

// 从 time_point 取本地交易日
auto today = dateHolderFromTimePoint(std::chrono::system_clock::now());

// 从整数构建（常见于数据库日期字段）
auto d = dateHolderFromYYYYMMDD(20240315);    // {2024, 3, 15}
auto tomorrow = d + 1;
auto yesterday = d - 1;

// 日历天数差值（需链接 DateHolder.cpp）
int diff = tomorrow - yesterday;              // == 2

// 打印格式为 "YYYY-MM-DD"
std::cout << d << '\n';                       // "2024-03-15"

// 用于 unordered_map（hash 已特化）
std::unordered_map<DateHolder, double> pnl;
pnl[today] = 1234.56;
```

### ConstType 作为信道 tag

```cpp
// 来源：tm_examples 中多路信号分发模式（已简化）
// 假设一个 variant 同时传递两种含义不同的 double：
using AskPrice = basic::SingleLayerWrapperWithID<0, double>;
using BidPrice = basic::SingleLayerWrapperWithID<1, double>;

using PriceVariant = std::variant<AskPrice, BidPrice>;
// 两者都是 double，但通过 ID 在 variant 层面区分

AskPrice ask {100.5};
BidPrice bid {100.3};
PriceVariant v = ask;  // 正确，类型安全
```

### VoidStruct 空信号

```cpp
// 来源：tm_examples/db_one_list_subscription/gui_client/GuiClientDataFlow.hpp:48（已简化）
TM_BASIC_CBOR_CAPABLE_EMPTY_STRUCT(GuiExitEvent);
// 等价于（空结构无字段，带序列化宏）：
// struct GuiExitEvent {};

// 用法：当 facility 不需要返回有意义的值时
using M = infra::RealTimeApp<TheEnvironment>;
auto exitFacility = M::template liftPure<basic::VoidStruct>(
    [](basic::VoidStruct &&) { /* 执行退出 */ return basic::VoidStruct {}; }
);
```

## 实时 / 回测行为差异

这些值类型本身不依赖 App 类型，实时与回测行为一致。

以下方面值得注意：

| 维度 | 实时 | 回测 |
|---|---|---|
| `DateHolder` 时区 | `dateHolderFromTimePoint` 取本地时区 | 回测时间戳通常是 UTC，应改用 `_Utc` 或 `_Zoned` 版本确保日期正确 |
| `FixedPrecisionShortDecimal` 精度 | 无差异 | 无差异 |
| 序列化格式 | 两端精度 N 必须匹配 | CBOR tuple 格式允许不同精度端互通（`fromPrecisionAndValue`） |

## 易错点

**1. `FixedPrecisionShortDecimal` 乘除不提供**  
该类型只提供加法、减法和取负。乘除因会产生精度问题（结果需要不同的精度参数），需要先提取底层整数 `.value()` 手动运算，再用 `FixedPrecisionShortDecimal(raw)` 重新构造，或转为 `double` 运算后再转回。常见错误：尝试 `p * q` 直接计算两价格之积（市值），应该是 `FixedPrecisionShortDecimal<P>::fromIntegral(p.value() * q_int / factor)`。

**2. `DateHolder` 加减运算需要链接 `DateHolder.cpp`**  
`operator-`（天数差）、`operator+`（偏移天数）、`dateHolderFromZonedTimePoint` 均是 `extern` 声明（`:81`、`:85–88`），实现在对应 `.cpp` 中，依赖 `date/tz` 库。只包含头文件而不链接会得到未定义符号错误。

**3. `ConstType<N>` 不携带任何数据，不能用于传递信息**  
`ConstType<N>` 是编译期 tag，实例不携带任何运行期数据。将它用于"带 int 的信号"时应改用 `ConstValueType<int, value>`（仍是编译期常量）或普通的 `int`。

**4. `SingleLayerWrapperWithID<N,T>` 的 N 是逻辑区分，不影响 CBOR 格式**  
序列化层对 `SingleLayerWrapperWithID<N,T>` 直接透传内层值，N 在 wire 上不可见。若接收端需要识别是哪个 ID，必须通过上层协议（消息类型、topic 等）传递，不能依赖反序列化时恢复 N。

**5. `DateHolder` 没有内置的 CBOR 序列化宏**  
不能直接将 `DateHolder` 放进带 `_SERIALIZE` 宏的结构体的字段清单，因为它没有 `StructFieldInfo` 反射。应在外层结构里用 `int`（`YYYYMMDD` 格式）存储日期，在应用层用工厂函数互转，或对 `DateHolder` 手写 `RunCBORSerializer` 特化。

**6. `FixedPrecisionShortDecimal` 的 `double` 构造会有舍入**  
`explicit FixedPrecisionShortDecimal(double d)` 使用 `std::llrint` 四舍五入，不是截断。在高频场景下频繁构造（如每 tick 从 double 价格创建）会有舍入行为；更准确的做法是从字符串或底层整数构造，完全绕过 double。

## 第三方依赖

- **Boost.LexicalCast** — `FixedPrecisionShortDecimal.hpp:8` 引入，用于字符串解析（`parseMantissa` 内部）。官方文档：https://www.boost.org/doc/libs/release/libs/lexical_cast/doc/html/index.html
- **date/tz（Howard Hinnant 的 date 库）** — `DateHolder.cpp` 中 `dateHolderFromZonedTimePoint` 使用，提供 IANA 时区支持。官方文档：https://howardhinnant.github.io/date/tz.html。vcpkg 包名：`date[tz]`。在仅使用本地/UTC 时间时可不依赖此库。
- **Boost.Preprocessor** — `ConstStringType.hpp` 在 MSVC + C++17 下用 `BOOST_PP_FOR` 展开字符串字面量为字符参数包（`:52–95`）。C++20 下使用 NTTPstring，无此依赖。

## 相关章节

- [序列化宏与结构反射](02-struct-field-info.md) — `StructFieldInfo`，`FixedPrecisionShortDecimal` 通过 `ConvertibleWithString` 接入反射系统
- [序列化格式](03-serialization.md) — `EncodableThroughMultipleProxies` 机制；`FixedPrecisionShortDecimal` 的 CBOR/JSON/Proto 三格式编解码
- [CSV / HDF5 / FlatPack](07-csv-hdf5-flatpack.md) — 含 `FixedPrecisionShortDecimal` 字段的结构体在 CSV 中以字符串读写，在 HDF5 中以 double 读写
- [时间与数据包装](../tm_infra/07-time-and-data.md) — `std::chrono::system_clock::time_point` 与 `DateHolder` 的关系
