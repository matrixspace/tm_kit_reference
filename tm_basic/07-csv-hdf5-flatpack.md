---
title: CSV / HDF5 / FlatPack / DynamicView
library: tm_basic
headers: [tm_kit/basic/StructFieldInfoBasedCsvUtils.hpp, tm_kit/basic/StructFieldInfoBasedHdf5Utils.hpp, tm_kit/basic/StructFieldInfoBasedFlatPackUtils.hpp, tm_kit/basic/StructFieldInfoBasedDynamicView.hpp]
keywords: [StructFieldInfoBasedSimpleCsvOutput, StructFieldInfoBasedSimpleCsvInput, StructFieldInfoBasedCsvImporterFactory, StructFieldInfoBasedCsvExporterFactory, StructFieldInfoBasedCsvInputOption, IsStructFieldInfoBasedCsvCompatibleStruct, StructFieldInfoBasedHdf5Utils, StructFieldInfoBasedSimpleFlatPackOutput, StructFieldInfoBasedSimpleFlatPackInput, FlatPack, DynamicView, DynamicConstView, FieldOperationThroughAny, AnyIter, CSV, HDF5, FlatPack, 批量IO, 动态视图, 字段遍历]
---

# CSV / HDF5 / FlatPack / DynamicView

## 用途

`tm_basic` 提供四类基于 `StructFieldInfo` 反射的批量 I/O 与运行期字段访问工具：

- **CSV** — 带表头的文本格式，支持读写、导入器/导出器节点、可选表头处理策略
- **HDF5** — 二进制列存格式，支持大规模顺序追加写入与一次性批量读取
- **FlatPack** — 紧凑二进制流格式，用于进程间或文件中的高性能序列化，字段类型支持比 CSV 更窄
- **DynamicView** — 运行期字段访问代理，通过字段名或索引以 `std::any` 读写 `StructFieldInfo` 结构体字段，无需编译期知道字段类型

四者均以 `StructFieldInfo<T>` 反射为前提，不适用于没有 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE` 等宏的裸类型。

## 头文件与命名空间

```cpp
#include <tm_kit/basic/StructFieldInfoBasedCsvUtils.hpp>
#include <tm_kit/basic/StructFieldInfoBasedHdf5Utils.hpp>
#include <tm_kit/basic/StructFieldInfoBasedFlatPackUtils.hpp>
#include <tm_kit/basic/StructFieldInfoBasedDynamicView.hpp>

namespace dev::cd606::tm::basic::struct_field_info_utils  // 所有工具均在此命名空间
```

## 核心类型与签名

### 1. CSV 工具（`StructFieldInfoBasedCsvUtils.hpp`）

#### 支持的字段类型（`:69–81`）

`is_simple_csv_field_v<F>` 为 `true` 的类型：
- 算术类型（`int`、`double` 等）、`bool`
- `std::tm`、`DateHolder`、`std::chrono::system_clock::time_point`
- `std::string`
- 空类型（`VoidStruct`、`ConstType` 等）
- 满足 `IsConstStringType` 的类型
- 满足 `ConvertibleWithString<T>` 的类型（包括 `FixedPrecisionShortDecimal`）
- `SingleLayerWrapper<T>` 变体（透传内层类型）

复合支持检查（`StructFieldInfoCsvSupportChecker<T>`，`:119–265`）：
- `IsGoodForCsv` — 当且仅当所有字段均满足 `is_simple_csv_field_v` 或为 `std::array`/`std::optional`/`std::tuple`/带 `StructFieldInfo` 的嵌套结构体
- `CsvFieldCount` — 编译期字段展开总数（嵌套结构体和 array 均展开计算）

嵌套字段命名约定：
- `std::array<X,N>` 字段展开为 `field[0]`、`field[1]`……
- 嵌套结构体展开为 `outer.inner` 形式

#### 写入（`:StructFieldInfoBasedSimpleCsvOutput<T>`）

```cpp
template <class T>
class StructFieldInfoBasedSimpleCsvOutput {
public:
    static void writeHeader(std::ostream &os);   // 写列名行（含换行符）
    static void writeData(std::ostream &os, T const &t);   // 写一行数据
    static void writeDataCollection(std::ostream &os,
        typename std::vector<T>::const_iterator begin,
        typename std::vector<T>::const_iterator end);
};
```

#### 读取（`StructFieldInfoBasedSimpleCsvInput<T>`）

```cpp
template <class T>
class StructFieldInfoBasedSimpleCsvInput {
public:
    static bool readOne(std::istream &is, T &t);
    static bool readOneWithIdxDict(std::istream &is, T &t,
        std::vector<int> const &idxDict);   // idxDict 由 headerDictToIdxDict 生成
    static std::optional<std::unordered_map<std::string,int>>
        readHeader(std::istream &is);       // 返回 列名→字段索引 map
    static std::vector<int> headerDictToIdxDict(
        std::unordered_map<std::string,int> const &dict);
    static std::vector<int> translateHeaderDict(
        std::vector<std::string> const &headerVec,
        std::unordered_map<std::string,int> const &dict);
};
```

#### 框架节点工厂（`:1405`，`:1481`）

```cpp
template <class M>
class StructFieldInfoBasedCsvImporterFactory {
public:
    // timeExtractor: T const& -> typename M::TimePoint
    // option 控制表头处理策略
    // dict 仅 UseHeaderAsDict 时需要
    template <class TimeExtractor>
    static std::shared_ptr<typename M::template Importer<T>>
    createImporter(
        std::istream &is,
        TimeExtractor &&timeExtractor,
        StructFieldInfoBasedCsvInputOption option = StructFieldInfoBasedCsvInputOption::IgnoreHeader,
        std::optional<std::unordered_map<std::string,int>> dict = std::nullopt
    );
};

template <class M>
class StructFieldInfoBasedCsvExporterFactory {
public:
    static std::shared_ptr<typename M::template Exporter<T>>
    createExporter(std::ostream &os, bool dontWriteHeader = false);
};

// 编译期检查（:1508）
template <class T>
inline constexpr bool IsStructFieldInfoBasedCsvCompatibleStruct =
    StructFieldInfoCsvSupportChecker<T>::IsGoodForCsv;
```

#### 表头策略枚举

```cpp
enum class StructFieldInfoBasedCsvInputOption {
    IgnoreHeader,    // 跳过第一行，按字段顺序读取（默认）
    HasNoHeader,     // 文件无表头，直接按顺序读取
    UseHeaderAsDict  // 读取并解析表头，按列名映射读取（字段可乱序）
};
```

---

### 2. HDF5 工具（`StructFieldInfoBasedHdf5Utils.hpp`）

#### 支持的字段类型（`:22–179`）

`StructFieldInfoBasedHdf5Support<T>::HasSupport == true` 的类型：
- `uint8/16/32/64_t`、`int8/16/32/64_t`、`char`、`bool`、`float`、`double`
- `std::array<T,N>`（当 `T` 本身有 HDF5 支持时）— 映射为 HDF5 ArrayType
- 带字符串表示的 `enum`（`IsEnumWithStringRepresentation`）— 映射为 HDF5 EnumType
- 具有 `StructFieldInfo` + `StructFieldOffsetInfo` 反射的结构体（当所有字段均有支持时）— 映射为 HDF5 CompType

> **注意**：HDF5 需要 `StructFieldOffsetInfo<T>::HasGeneratedStructFieldOffsetInfo` 为 `true`（`:141`）。标准的 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE` 宏同时生成字段偏移信息，通常满足此条件。`DateHolder`、`std::string`、`ConvertibleWithString` 类型没有 HDF5 支持。

#### 公共 API（`StructFieldInfoBasedHdf5Utils<T>`，`:183`）

```cpp
template <class T>
class StructFieldInfoBasedHdf5Utils {
public:
    // 获取 T 对应的 HDF5 复合类型描述符
    static H5::DataType hdf5DataType();

    // 打开或创建可扩展 dataset（maxSize=H5S_UNLIMITED 则无限制）
    static std::unique_ptr<H5::DataSet> openOrCreateEmpty(
        H5::H5File *file,
        std::string const &datasetName,   // 支持 "group/subgroup/name" 路径
        hsize_t maxSize  = H5S_UNLIMITED,
        hsize_t chunkSize = 10000
    );

    // 删除 dataset（不存在则静默忽略）
    static void deleteDataSet(H5::H5File *file, std::string const &datasetName);

    // 整体写入（先删旧数据，再创建新 dataset 并写入）
    static void write(std::vector<T> const &data,
                      std::string const &fileName,
                      std::string const &datasetName);

    // 整体读取（文件或 dataset 不存在时返回空 vector）
    static void read(std::vector<T> &data,
                     std::string const &fileName,
                     std::string const &datasetName);

    // 追加（使用已打开的 dataset）— 高性能批量追加场景
    static void append(std::vector<T> const &data,
                       std::unique_ptr<H5::DataSet> const &dataset);
    static void append(T const &data,
                       std::unique_ptr<H5::DataSet> const &dataset);

    // 追加（按文件名/dataset 名，内部 openOrCreateEmpty）
    static void append(std::vector<T> const &data,
                       std::string const &fileName,
                       std::string const &datasetName,
                       hsize_t maxSize   = H5S_UNLIMITED,
                       hsize_t chunkSize = 10000);
    static void append(T const &data, std::string const &fileName,
                       std::string const &datasetName,
                       hsize_t maxSize   = H5S_UNLIMITED,
                       hsize_t chunkSize = 10000);
};
```

---

### 3. FlatPack 工具（`StructFieldInfoBasedFlatPackUtils.hpp`）

#### 支持的字段类型（`:14`）

`is_simple_flatpack_field_v<F>` 为 `true` 的类型（**比 CSV 更窄**）：
- 算术类型（`int`、`double` 等）
- 空类型
- `std::string`（编码为 4 字节大端 uint32_t 长度前缀 + 原始字节）
- `ByteData`
- `SingleLayerWrapper<T>` 变体（透传内层）

CSV 支持但 FlatPack **不支持**的类型：`DateHolder`、`std::tm`、`std::chrono::system_clock::time_point`、`ConvertibleWithString`（包括 `FixedPrecisionShortDecimal`）。

#### 低级 I/O（`StructFieldInfoBasedSimpleFlatPackOutput<T>` / `Input<T>`）

```cpp
template <class T>
class StructFieldInfoBasedSimpleFlatPackOutput {
public:
    static void writeData(std::ostream &os, T const &t);  // :178
    static void writeDataCollection(std::ostream &os,
        typename std::vector<T>::const_iterator begin,
        typename std::vector<T>::const_iterator end);
};

template <class T>
class StructFieldInfoBasedSimpleFlatPackInput {
public:
    // 从 string_view 的 start 偏移处解析一个 T，返回消耗字节数
    static std::optional<std::size_t> readOne(
        std::string_view const &sv, std::size_t start, T &output);
    static bool read(std::istream &is, T &output);
};
```

#### 高级包装类：`FlatPack<T*>` / `FlatPack<T const*>` / `FlatPack<shared_ptr<const T>>`（`:553`，`:620`，`:658`）

这三个特化提供与 `Proto<T>` / `Json<T>` 兼容的接口，可直接接入 `RunSerializer`：

```cpp
// 示例：FlatPack<T const*>（其他两个变体接口相同）
template <class T>
class FlatPack<T const *> {
public:
    FlatPack(T const *t);

    void writeToStream(std::ostream &os) const;
    void writeToString(std::string &s) const;
    bool SerializeToString(std::string *s) const;  // RunSerializer 入口

    static std::optional<FlatPack<T const*>> fromStringView(std::string_view const &sv);
    static bool ParseFromString(std::string_view const &sv, T &output);  // RunDeserializer 入口

    T const *value() const;
    T const &operator*() const;
    T const *operator->() const;
};
```

FlatPack 不注册 `RunSerializer` / `RunDeserializer`，需要手动调用 `SerializeToString` / `ParseFromString`，或通过 `DirectlySerializableChecker` 检查并手动使用。

---

### 4. DynamicView（`StructFieldInfoBasedDynamicView.hpp`）

#### `DynamicView<T>`（可变，`:537`）

```cpp
template <class T,
    typename=std::enable_if_t<StructFieldInfo<T>::HasGeneratedStructFieldInfo>>
class DynamicView {
public:
    DynamicView(T &t);

    // 运行期字段访问（返回可赋值代理，支持 operator= 与 operator*）
    internal::AssignableFromAnyByName<T> operator[](std::string_view const &s);
    internal::AssignableFromAnyByIdx<T>  operator[](std::size_t idx);

    // 遍历所有字段到输出迭代器（tuple<string_view, any>）
    template <class OutIter> void copyNamesAndValuesTo(OutIter iter) const;
    // 遍历所有字段值（any）
    template <class OutIter> void copyValuesTo(OutIter iter) const;
    // 批量设置（从 (name, any) 序列）
    template <class Iter> void copyFromNamesAndValues(Iter begin, Iter end);
    // 批量设置（从 any 序列，按位置对应）
    template <class Iter> void copyFromValues(Iter begin, Iter end);

    // 类型安全读取（类型不匹配返回 nullopt）
    template <class X> std::optional<X> get(std::string_view const &s) const;
    template <class X> std::optional<X> get(std::size_t idx) const;
    // 类型安全写入（类型不匹配返回 false）
    template <class X> bool set(std::string_view const &s, X const &x);
    template <class X> bool set(std::size_t idx, X const &x);

    // 遍历所有字段：F 可接受 (any)、(name, any) 或 (idx, name, any)
    template <class F> void forAll(F &&f) const;
    // 遍历特定类型字段（F 接受 (X)、(name, X) 或 (idx, name, X)）
    template <class X, class F> void forAllByType(F &&f) const;
    // 可变遍历特定类型字段
    template <class X, class F> void updateAllByType(F &&f);

    // 编译期字段名访问（ConstFieldName 为 TM_BASIC_CONST_STRING_TYPE 生成的类型）
    template <class ConstFieldName> auto returnOneByName();
    template <class ConstFieldName, class X> auto setOneByName(X const &x);
    template <class ConstFieldName, class F> auto forOneByName(F &&f);
    template <class ConstFieldName, class F> auto updateOneByName(F &&f);
};
```

#### `DynamicConstView<T>`（只读，`:619`）

提供 `DynamicView` 的只读子集：`operator[]`（返回 `optional<any>`）、`copyNamesAndValuesTo`、`copyValuesTo`、`get<X>`、`forAll`、`forAllByType`、`returnOneByName`。

#### 代理类型

`AssignableFromAnyByName<T>` / `AssignableFromAnyByIdx<T>`（`:484`，`:510`）是 `DynamicView::operator[]` 返回的代理：
- `operator=(any const &)` 或 `operator=(X const &)` — 写入字段
- `operator*()` — 读取字段当前值（返回 `any`）
- `operator bool()` — 字段是否存在

## 最小可用示例

### CSV 导入器：从文件读取行情快照

```cpp
// 来源：tm_examples/simple_demo/plain_executables（已简化）
#include <tm_kit/basic/StructFieldInfoBasedCsvUtils.hpp>
using namespace dev::cd606::tm::basic::struct_field_info_utils;

TM_BASIC_CBOR_CAPABLE_STRUCT(TickData,
    ((std::string, symbol))
    ((double, price))
    ((int64_t, volume))
);
TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE_NO_FIELD_NAMES(TickData,
    ((std::string, symbol))((double, price))((int64_t, volume))
);

// 直接批量读取（不经过框架节点）
std::ifstream f("ticks.csv");
StructFieldInfoBasedSimpleCsvOutput<TickData>::writeHeader(f); // 仅写入时
TickData t;
while (StructFieldInfoBasedSimpleCsvInput<TickData>::readOne(f, t)) {
    process(t);
}

// 在图中使用（RealTimeApp 或 SinglePassIterationApp）
using M = infra::TopDownSinglePassIterationApp<TheEnvironment>;
std::ifstream csvFile("ticks.csv");
auto importer = StructFieldInfoBasedCsvImporterFactory<M, TickData>::createImporter(
    csvFile,
    [](TickData const &t) { return TheEnvironment::resolveTime(/* 时间戳字段 */); },
    StructFieldInfoBasedCsvInputOption::IgnoreHeader
);
r.registerImporter("tick_importer", importer);
```

### HDF5：追加写入行情数据

```cpp
// 来源：tm_examples 中历史数据存储模式（已简化）
#include <tm_kit/basic/StructFieldInfoBasedHdf5Utils.hpp>
using HDF5 = struct_field_info_utils::StructFieldInfoBasedHdf5Utils<TickData>;

// 追加单条（自动打开或创建 dataset）
HDF5::append(tick, "market.h5", "/2024/ticks");

// 高性能批量追加：复用已打开的 dataset
auto file    = std::make_unique<H5::H5File>("market.h5", H5F_ACC_RDWR|H5F_ACC_CREAT);
auto dataset = HDF5::openOrCreateEmpty(file.get(), "/2024/ticks");
for (auto const &batch : batches) {
    HDF5::append(batch, dataset);  // 不反复开关文件
}

// 批量读取
std::vector<TickData> all;
HDF5::read(all, "market.h5", "/2024/ticks");
```

### FlatPack：二进制流序列化

```cpp
// 来源：tm_examples 中 socket 直连传输模式（已简化）
#include <tm_kit/basic/StructFieldInfoBasedFlatPackUtils.hpp>
using namespace dev::cd606::tm::basic::struct_field_info_utils;

// 低级写入
std::ostringstream oss;
StructFieldInfoBasedSimpleFlatPackOutput<TickData>::writeData(oss, tick);
std::string payload = oss.str();

// 低级读取（从网络缓冲区 string_view 的 offset 开始解析）
TickData out;
auto consumed = StructFieldInfoBasedSimpleFlatPackInput<TickData>::readOne(
    std::string_view{buf.data(), buf.size()}, 0, out
);

// 通过指针包装器（避免拷贝）
TickData tick = ...;
FlatPack<TickData const*> fp(&tick);
std::string s;
fp.SerializeToString(&s);   // 序列化

TickData recovered;
FlatPack<TickData const*>::ParseFromString(std::string_view{s}, recovered);
```

### DynamicView：按字段名动态处理

```cpp
// 来源：tm_examples/db_one_list_subscription（已简化）
#include <tm_kit/basic/StructFieldInfoBasedDynamicView.hpp>
using namespace dev::cd606::tm::basic::struct_field_info_utils;

TickData t {"BTC", 65000.0, 10};
DynamicView<TickData> view(t);

// 运行期按名读写
view["price"] = 65001.0;           // 通过代理赋值
double p = *view["price"];          // 通过代理读取（std::any）

// 类型安全读取
auto priceOpt = view.get<double>("price");  // optional<double>

// 遍历所有字段（F 接受 (name, any)）
view.forAll([](std::string_view name, std::any const &val) {
    std::cout << name << '\n';
});

// 遍历特定类型字段（例如将所有 double 字段加一）
view.updateAllByType<double>([](double &v) { v += 1.0; });

// 编译期字段名访问（零开销，无运行期查找）
view.setOneByName<TM_BASIC_CONST_STRING_TYPE("price")>(65002.0);
auto sym = view.returnOneByName<TM_BASIC_CONST_STRING_TYPE("symbol")>();

// DynamicConstView：只读版本
DynamicConstView<TickData> cview(t);
auto v = cview["volume"];  // optional<any>
```

## 实时 / 回测行为差异

这四个工具本身不依赖 App 类型，实时与回测行为一致。差异出现在与框架节点的集成上：

| 工具 | 实时模式 | 回测模式 |
|---|---|---|
| `CsvImporterFactory` | 通常用于生产环境不是主路径，但语法相同 | 常用于回测数据源；importer 驱动单程迭代 |
| `CsvExporterFactory` | 输出日志或结果文件 | 输出回测结果，不受时钟驱动 |
| HDF5 `append` | 实时追加，需注意多线程文件写竞争 | 单线程无竞争，吞吐量高 |
| FlatPack | 常用于 socket/内存通信序列化 | 常用于回测快照文件 |
| DynamicView | 两种模式完全一致，纯 CPU 操作 | 同上 |

## 易错点

**1. FlatPack 不支持 `DateHolder` 和 `FixedPrecisionShortDecimal`**  
FlatPack 的 `is_simple_flatpack_field_v` 比 CSV 更窄——不包含 `DateHolder`、`std::tm`、`ConvertibleWithString`（即 `FixedPrecisionShortDecimal` 也不支持）。含这些字段的结构体在 FlatPack 时编译失败，报错在 `StructFieldInfoFlatPackSupportChecker::IsGoodForFlatPack` 的 `static_assert` 处。解决方法：将 `DateHolder` 替换为 `int`（YYYYMMDD），`FixedPrecisionShortDecimal` 替换为 `int64_t`（底层整数）。

**2. HDF5 需要 `StructFieldOffsetInfo`（字段偏移信息）**  
`StructFieldInfoBasedHdf5Support` 对结构体的特化（`:141`）同时要求 `StructFieldInfo<T>::HasGeneratedStructFieldInfo` 和 `StructFieldOffsetInfo<T>::HasGeneratedStructFieldOffsetInfo`。标准的序列化宏（如 `TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE`）通常同时生成两者，但若只调用了 `TM_BASIC_CBOR_CAPABLE_STRUCT` 而没有 `_SERIALIZE` 宏，可能只有 `StructFieldInfo`。遇到 `HasSupport == false` 时，先检查是否生成了偏移信息。

**3. CSV 的 `std::string` 字段不转义逗号和引号**  
`writeData` 使用简单逗号分隔，不实现 RFC 4180 的引号转义。如果 `std::string` 字段内容含逗号或换行符，输出的 CSV 会错行。需要使用字段内容不含特殊字符的类型，或在写出前预处理。

**4. `UseHeaderAsDict` 模式下列顺序可以与字段定义不同，但字段名必须完全匹配**  
`UseHeaderAsDict` 读取文件表头后按名映射到字段，可应对列顺序乱序的文件，但字段名拼写必须与 `StructFieldInfo<T>::FIELD_NAMES` 完全匹配（区分大小写）。嵌套字段的列名必须写成 `outer.inner` 形式，数组字段写成 `field[0]`。

**5. HDF5 `write` 会删除旧数据集再重建**  
`write(vector, fileName, datasetName)` 先 `unlink` 旧 dataset 后重建，不是追加。若需要追加，必须用 `append` 族函数；若误用 `write`，之前写入的数据全部丢失。

**6. `DynamicView::operator[]` 返回代理，不是引用**  
`auto x = view["price"]` 返回 `AssignableFromAnyByName<T>` 代理对象，不是 `double&`。直接将代理对象传给期望 `double` 的函数会失败；应使用 `view.get<double>("price")` 获取 `optional<double>`，或 `std::any_cast<double>(*view["price"])` 解包 `any`。

**7. `DynamicView` 的 `forAll` 中 F 的签名必须与字段以 `any` 包装后的接口兼容**  
`forAll` 内部（`AnyIter::forAll`，`:267`）将每个字段值包装为 `std::any`，再以 `any` 传给 F。若 F 直接接受 `double const &` 而非 `std::any const &`，则 C++20 概念检查会失败（C++17 下 Boost.Hana 检查失败），编译报错。应使用 `forAllByType<double>(F)` 来处理特定类型的字段，或在 F 内部调用 `std::any_cast`。

## 第三方依赖

- **HDF5 C++ 库（`libhdf5_cpp`）** — `StructFieldInfoBasedHdf5Utils.hpp:7` 引入 `<hdf5.h>` 和 `<H5Cpp.h>`。HDF5 官方文档：https://docs.hdfgroup.org/hdf5/develop/；HDF5 C++ API 参考：https://docs.hdfgroup.org/hdf5/develop/group___h5_c_p_p.html。vcpkg 包名：`hdf5[cpp]`。
- **Boost.Algorithm / Boost.String** — `StructFieldInfoBasedHdf5Utils.hpp:10` 引入 `boost/algorithm/string.hpp`，用于数据集路径的分割与裁剪（`boost::split`、`boost::trim_copy`）。
- **Boost.Hana** — `StructFieldInfoBasedDynamicView.hpp:10`，C++17 下用于 `forAll` / `forAllByType` 中的成员函数存在性检测（C++20 下改用 Concept）。

## 相关章节

- [序列化宏与结构反射](02-struct-field-info.md) — `StructFieldInfo<T>`、`StructFieldOffsetInfo<T>`、`TM_BASIC_CBOR_CAPABLE_STRUCT_SERIALIZE` 宏族
- [量化值类型](06-value-types.md) — `FixedPrecisionShortDecimal`（CSV 可用，FlatPack 不可用）；`DateHolder`（CSV 可用，HDF5/FlatPack 不可用）
- [序列化格式](03-serialization.md) — `RunSerializer`/`RunDeserializer`；`FlatPack` 未注册到该体系，需手动调用
- [共享链](08-shared-chain.md) — `simple_shared_chain` 的持久化后端有时配合 FlatPack 或 HDF5 使用
- [CommonFlowUtils](05-common-flow-util.md) — `CsvImporterFactory`/`CsvExporterFactory` 创建的节点通过 `AppRunner` 连接到 CommonFlowUtils 的各类处理节点
