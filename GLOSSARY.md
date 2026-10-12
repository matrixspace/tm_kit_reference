---
title: 术语表
library: meta
headers: []
keywords: [术语, glossary, 中英对照, importer, exporter, action, facility]
---

# TM Kit 术语表

本表是全套文档的译名与用词标准。各章节不得自创译名；发现缺项时补充到本表。

## 数据流图基础

| 英文 | 中文 | 说明 |
|---|---|---|
| data-flow graph | 数据流图 | TM Kit 的核心模型：程序被表达为节点与连边构成的图 |
| importer | importer（导入节点） | 无上游、只产出数据的节点，把外部世界的数据引入图中 |
| exporter | exporter（导出节点） | 无下游、只消费数据的节点，产生图外副作用 |
| action | action（动作节点） | 有上游也有下游，负责变换数据 |
| node | 节点 | importer / exporter / action / facility 的统称 |
| source | source | `AppRunner` 中代表"可被连接的输出端"的句柄 |
| sink | sink | `AppRunner` 中代表"可被连接的输入端"的句柄 |
| connect | 连接 | 把一个 source 接到一个 sink 上 |

## 按单设施族

| 英文 | 中文 | 说明 |
|---|---|---|
| on-order facility | on-order facility（按单设施） | 接受带 tag 的输入，对每个输入产出零个或多个同 tag 输出；允许图中成环 |
| local on-order facility | local on-order facility | facility + exporter 的捆绑，额外接收辅助输入 |
| on-order facility with external effects | 带外部效应的 facility | facility + importer 的捆绑 |
| VIE on-order facility | VIE facility | facility + importer + exporter 的三合一捆绑（VIE = variable interest entity） |
| facilitioid | facilitioid | 可当作 facility 使用的连接器抽象，见 `FacilitioidConnector` |
| place order | 下单 | 向 facility 投递一个带 tag 的请求 |
| tag / key | tag / key | `Key<T,Env>` 为输入附加的唯一标识，用于把响应匹配回请求 |

## 时间与数据包装

| 英文 | 中文 | 说明 |
|---|---|---|
| time point | 时间点 | 环境的 `TimePointType`，实时模式下通常是 `std::chrono::system_clock::time_point` |
| lift | 提升（lift） | 把普通函数包装成图中节点的操作，如 `liftPure` |
| kleisli | kleisli | 直接操作带时间戳数据包的函数形态，可控制输出时间与是否产出 |
| pure / maybe / multi | pure / maybe / multi | lift 的三类形态：必定产出一个 / 可能不产出 / 产出多个 |
| enhanced | enhanced | lift 变体，函数额外收到时间戳 |
| final flag | final 标记 | 数据包上标记"这是本流的最后一个数据" |
| version checker | 版本检查 | 丢弃版本倒退数据的机制，见 `VersionChecker` |

## 运行模式

| 英文 | 中文 | 说明 |
|---|---|---|
| real time mode | 实时模式 | `RealTimeApp`，多线程、挂钟时间驱动 |
| single pass iteration mode | 单遍迭代模式 | `SinglePassIterationApp` / `TopDownSinglePassIterationApp`，单线程、数据驱动，用于回测 |
| backtest | 回测 | 用历史数据在单遍迭代模式下复跑业务逻辑 |
| virtual / simulated time | 虚拟时间 | 实时模式下用加速或对齐后的时钟驱动 |
| environment | 环境（Environment） | 若干 component 的虚继承混合，承载时钟、日志、ID、传输等能力 |
| component | 组件（component） | 可插入 Environment 的能力单元 |
| app runner | AppRunner | 负责注册节点、连接、校验、输出 Graphviz、启动图的对象 |
| touchup | touchup | 延迟到 finalize 阶段执行的图修补回调 |

## 序列化与结构反射

| 英文 | 中文 | 说明 |
|---|---|---|
| struct field info | 结构字段信息 | 编译期结构反射基础设施，由宏生成 |
| byte data | ByteData | 字节缓冲包装类型 |
| CBOR | CBOR | TM Kit 的默认二进制序列化格式，自行实现 |
| proto interop | proto 互操作 | 不依赖 protoc 生成代码、直接按 protobuf wire format 读写 |
| topic | topic | 广播消息的主题字符串 |

## 传输与链

| 英文 | 中文 | 说明 |
|---|---|---|
| connection locator | 连接定位符 | 统一的传输地址字符串，如 `rabbitmq://host::user:pass:queue[opts]` |
| broadcast | 广播 | 一对多的发布订阅通信 |
| remote facility | 远程 facility | 跨进程的请求响应式 facility |
| heartbeat | 心跳 | 周期性状态广播，也用于服务发现 |
| alert | 告警 | 带日志级别的事件广播 |
| shared chain | 共享链 | 可被多进程追加与读取的持久化单向链表，用作事件溯源存储 |
| chain folder | chain folder | 把链上数据折叠成状态的函数对象 |
| transaction | 事务 | 带版本校验的状态读写协议，见 tm_basic 的 transaction 模块 |
| identity checker | 身份校验 | 对 facility 调用方附加/校验身份的组件 |
