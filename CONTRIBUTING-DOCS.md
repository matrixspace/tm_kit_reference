---
title: 文档写作规范
library: meta
headers: []
keywords: [规范, 写作, front-matter, 引用格式]
---

# TM Kit 参考文档写作规范

本文件是 `tm_kit_reference/` 的内部写作规范。所有章节作者（人类或 agent）在动笔前必须先读本文件。

## 0. 两类读者

1. **人类开发者**：需要快速定位"我要做 X，该用哪个类、怎么写、有什么坑"。
2. **大模型检索**：需要稳定的 front-matter 关键词、自包含的小节、可点击的源码引用。

因此：每个小节都要能被单独截取使用，不依赖上文；同时全文要有连贯的阅读顺序。

## 1. 统一节序

每篇章节文档按以下顺序组织（没有内容的小节直接省略，不要留空壳）：

1. **用途** —— 一两句话说明这个模块解决什么问题，什么时候该用它。
2. **头文件与命名空间** —— 列出 `#include` 路径和完整命名空间。
3. **核心类型与签名** —— 关键类/模板/函数的真实签名，附源码行号引用。
4. **最小可用示例** —— 必须出自或改写自 `tm_examples/`，并注明来源路径。
5. **实时 / 回测行为差异** —— 本模块在 `RealTimeApp` 与 `(TopDown)SinglePassIterationApp` 下的差异。量化场景的核心关切，**凡有差异必须写**。
6. **易错点** —— 实际会导致 BUG 的地方：生命周期、线程、时间倒流、类型推导失败等。
7. **第三方依赖** —— 用到的第三方库 + 官方文档链接。
8. **相关章节** —— 指向其他文档的相对链接。

## 2. Front-matter

每篇文档开头必须有 YAML front-matter：

```yaml
---
title: 中文标题
library: tm_infra | tm_basic | tm_transport | meta
headers: [tm_kit/infra/RealTimeApp.hpp, ...]   # 本篇覆盖的头文件
keywords: [中英文关键词, 便于检索]
---
```

`headers` 用于回答"这个头文件的文档在哪"，`keywords` 用于语义检索。两者都要尽量全。

## 3. 源码引用格式

一律写成 `path/to/file.hpp:123`（相对于仓库根目录），终端里可点击：

> `Environment` 是组件的虚继承混合，见 `tm_infra/tm_kit/infra/Environments.hpp:11`。

- 引用类型/函数定义时给出行号；引用整个模块时只给文件路径。
- **行号必须真实**。写作时用 `grep -n` 核对，不要凭记忆写。
- 跨库引用也用同样格式。

## 4. 示例代码纪律

**绝对禁止编造 API。** 这是本套文档最重要的一条。

- 示例必须来自 `tm_examples/` 下的真实代码，节选或简化后注明来源：

  ```cpp
  // 来源：tm_examples/simple_demo/plain_executables/MainLogic.cpp:40
  using TheEnvironment = infra::Environment<
      infra::CheckTimeComponent<false>,
      infra::TrivialExitControlComponent,
      basic::TimeComponentEnhancedWithBoostTrivialLogging<basic::real_time_clock::ClockComponent>,
      ...
  >;
  ```

- 若为了说明而简化了示例，注明"（已简化）"。
- 若某特性在 `tm_examples/` 中找不到用例，**不要臆造调用方式**：直接引用头文件中的真实签名，并注明"示例代码库中暂无用例"。
- 签名一律从源码复制，不要手写重排模板参数。

## 5. 语言与术语

- 正文用中文，句子简短。
- API 名、类型名、宏名、命名空间保持英文原样，不翻译：`liftPure`、`FacilitioidConnector`、`OnOrderFacility`。
- 概念术语首次出现时给中英对照，之后统一用英文：on-order facility（按单设施）。
- 所有术语必须登记到 [GLOSSARY.md](GLOSSARY.md)，不要在各章节自创译名。

## 6. 实时 / 回测对照的写法

这是 TM Kit 的立身之本，也是最容易出 BUG 的地方。锚点示例是
`tm_examples/simple_demo/plain_executables/MainLogic.cpp`——同一文件里
`run_real_or_virtual()` 与 `run_backtest()` 用两套 Environment，业务逻辑
`MainLogicCombination` 完全复用。

写这类小节时用表格对照：

| 维度 | RealTimeApp | TopDownSinglePassIterationApp |
|---|---|---|
| ... | ... | ... |

## 7. 篇幅

- 单篇目标 150–500 行。超过 500 行考虑拆分并在 README 索引中登记。
- 不写与代码重复的内容（逐个字段罗列 struct 成员意义不大，除非字段语义不显然）。
- 不写安装与构建步骤——那些在仓库根 `CLAUDE.md` 里，需要时链接过去。

## 8. 交付前自检

- [ ] front-matter 四个字段齐全
- [ ] 所有 `file.hpp:line` 引用的文件真实存在、行号对得上
- [ ] 所有相对链接可解析
- [ ] 示例代码均有来源标注，无编造 API
- [ ] 有"实时/回测差异"小节（或已确认本模块无差异并说明）
- [ ] 术语已登记到 GLOSSARY.md
