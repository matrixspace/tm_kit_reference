---
title: tm_basic 概览
library: tm_basic
headers: [tm_kit/basic/AppRunnerUtils.hpp, tm_kit/basic/CommonFlowUtils.hpp, tm_kit/basic/ByteData.hpp, tm_kit/basic/SerializationHelperMacros.hpp]
keywords: [tm_basic, overview, 概览, 序列化, 时钟, 日志, CommonFlowUtils, AppRunnerUtils]
---

# tm_basic 概览

## 用途

`tm_basic` 是 TM Kit 的第二层，依赖 `tm_infra` 并为其提供：

- **时钟实现** — 四套适配不同 App 类型的时钟组件
- **序列化基础设施** — 宏驱动的结构反射、CBOR/Proto/JSON 互操作
- **日志组件** — 封装 spdlog 和 Boost.Log 的日志混入
- **通用流工具** — `CommonFlowUtilComponents`：keyify、delayer、dispatcher、版本检查等
- **量化常用类型** — `FixedPrecisionShortDecimal`、`DateHolder`、`ConstType`
- **批量 I/O** — CSV、HDF5、FlatPack、DynamicView
- **共享链** — `simple_shared_chain`：跨进程事件溯源存储的读写抽象
- **事务协议** — `transaction` v2：版本化键值读写
- **AppRunner 工具** — `AppRunnerUtils`、`MultiAppRunnerUtils`、`GraphControlFacility`

## 依赖链

```
tm_infra  ←  tm_basic  ←  tm_transport
```

`tm_basic` 不依赖任何第三方传输库，但序列化组件依赖 Boost.Preprocessor（用于宏展开）和可选的 spdlog、nlohmann_json、simdjson。

## 头文件组织

```
tm_kit/basic/
├── 时钟
│   ├── real_time_clock/            RealTimeApp 用，挂钟时间
│   ├── single_pass_iteration_clock/ SinglePassIterationApp 用，数据驱动
│   ├── top_down_single_pass_iteration_clock/  TopDownSinglePassIterationApp 用（=single_pass）
│   └── empty_clock/                BasicWithTimeApp 用，无时钟
├── 序列化
│   ├── SerializationHelperMacros.hpp  宏族：TM_BASIC_CBOR_CAPABLE_STRUCT 等
│   ├── ByteData.hpp                   ByteData/ByteDataView/ByteDataWithTopic/ByteDataWithID
│   │                                  + RunCBORSerializer/RunCBORDeserializer 全族特化
│   ├── ProtoInterop.hpp               protobuf wire-format 互操作（无 protoc）
│   └── NlohmannJsonInterop.hpp        nlohmann_json 编解码 + simdjson 快速解码
│                                      （simdjson 无独立头文件，见 read_simd 系列）
├── 日志
│   ├── LoggingComponentBase.hpp       抽象基类
│   ├── SpdLoggingComponent.hpp        spdlog 实现 + TimeComponentEnhancedWithSpdLogging
│   └── TrivialBoostLoggingComponent.hpp  Boost.Log 实现 + TimeComponentEnhancedWithBoostTrivialLogging
├── 通用流
│   └── CommonFlowUtils.hpp            CommonFlowUtilComponents<M> 工具族
├── 量化类型
│   ├── FixedPrecisionShortDecimal.hpp
│   ├── DateHolder.hpp
│   └── ConstType.hpp / ConstValueType.hpp / ConstStringType.hpp
├── 批量 I/O
│   ├── StructFieldInfoBasedCsvUtils.hpp
│   ├── StructFieldInfoBasedHdf5Utils.hpp
│   ├── StructFieldInfoBasedFlatPackUtils.hpp
│   └── StructFieldInfoBasedDynamicView.hpp
├── 共享链
│   └── simple_shared_chain/           ChainReader / ChainWriter / InMemory 实现等
├── 事务
│   └── transaction/                   TransactionClient / TransactionFacility
└── AppRunner 工具
    ├── AppRunnerUtils.hpp             AppRunnerUtilComponents<R>
    └── MultiAppRunnerUtils.hpp
```

## 使用入口

选择时钟组件时，先确认 App 类型，再选对应命名空间：

| App 类型 | 时钟命名空间 |
|---|---|
| `RealTimeApp` | `basic::real_time_clock::ClockComponent` |
| `SinglePassIterationApp<Env,TimePoint>` | `basic::single_pass_iteration_clock::ClockComponent<TimePoint>` |
| `TopDownSinglePassIterationApp` | `basic::top_down_single_pass_iteration_clock::ClockComponent<TimePoint>`（等同上一行） |
| `BasicWithTimeApp` | `basic::empty_clock::ClockComponent<TimePoint>` |

日志组件通常以 `TimeComponentEnhancedWithXxxLogging<ClockComponent>` 的形式把时钟和日志合并：

```cpp
// 实时模式（来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40）
basic::TimeComponentEnhancedWithBoostTrivialLogging<
    basic::real_time_clock::ClockComponent
>

// 回测模式（来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:191）
basic::top_down_single_pass_iteration_clock::ClockComponent<
    std::chrono::system_clock::time_point
>
// 回测下通常单独使用 TrivialBoostLoggingComponent，或不接日志组件
```

## 相关章节

- [时钟组件](01-clocks.md)
- [序列化宏与结构反射](02-struct-field-info.md)
- [序列化格式](03-serialization.md)
- [日志组件](04-logging.md)
- [CommonFlowUtils](05-common-flow-util.md)
- [量化值类型](06-value-types.md)
- [CSV / HDF5 / FlatPack](07-csv-hdf5-flatpack.md)
- [共享链](08-shared-chain.md)
- [事务协议](09-transaction.md)
- [AppRunnerUtils](10-app-runner-utils.md)
