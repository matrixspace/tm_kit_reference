---
title: 下游接入指南
library: meta
headers: []
keywords: [下游接入, downstream, submodule, AGENT_INDEX, CLAUDE.md, AGENTS.md, 版本 pin, CI, tm_docs]
---

# 下游接入指南

本仓库（`tm_kit_reference`）是 tm_kit 的完整开发参考文档，供依赖 tm_kit 的上层项目使用。上层项目同样由 agent 开发，所以接入的目标不只是"人能查到"，而是**agent 在正确的时机自动读到正确的那一篇**。

## 1. 核心约束

| 指标 | 值 |
|---|---|
| 全文 | 51 篇，约 1.6 万行，≈ 38 万 token |
| 单篇 | 3k–14k token |
| **常驻层** | `AGENT_INDEX.md`，≈ 5k token |

38 万 token 超过任何 agent 的上下文窗口，**不能整包投喂**。正确的分层是：

```
常驻   AGENT_INDEX.md       ← 每次会话都加载。铁律 + 任务路由表 + 章节清单
按需   51 篇文档             ← agent 按需 Read 单篇
检索   LOOKUP.md / tm_docs  ← grep 精确命中，不整篇读
```

`AGENT_INDEX.md` 里的"铁律"一节是投入产出比最高的部分——12 条 tm_kit 特有的坑，每条都会导致静默错误或难以定位的编译失败。

## 2. 接成 submodule

在**下游项目**的根目录：

```bash
git submodule add https://github.com/matrixspace/tm_kit_reference.git docs/tm_kit
git commit -m "add tm_kit docs as submodule"
```

克隆下游项目时记得带上子模块：

```bash
git clone --recurse-submodules <下游项目>
# 已经克隆过的话：
git submodule update --init --recursive
```

**升级文档**（下游显式决定何时跟进）：

```bash
cd docs/tm_kit
git fetch && git checkout <tag 或 commit>
cd ../..
git add docs/tm_kit
git commit -m "bump tm_kit docs to <版本>"
```

> **为什么用 submodule 而不是拷贝**：文档描述的是特定版本的 tm_kit API。submodule 让下游把文档版本与它依赖的 tm_kit 版本一起 pin 住，升级是一次有记录的提交；拷贝进仓库则多份副本会静默分叉。

## 3. 在下游 CLAUDE.md / AGENTS.md 里加一段

**这一步是整个接入的关键。** submodule 挂上去之后，agent 仍然不知道文档存在——必须有一段常驻文字告诉它。

把下面这段贴进下游项目的 `CLAUDE.md`（或 `AGENTS.md`）：

````markdown
## tm_kit 框架文档

本项目依赖 tm_kit（C++17 数据流框架）。完整参考文档在 `docs/tm_kit/`。

**写任何 tm_kit 代码之前，先读 `docs/tm_kit/AGENT_INDEX.md`** ——
里面有 12 条铁律（每条都会导致静默错误或难懂的编译失败）和任务→章节的路由表。

定位到某一篇后整篇读；不要一次加载多篇（单篇 3k–14k token，全量 38 万）。

检索方式：

    ./docs/tm_kit/tools/tm_docs find "事务 订阅"        # 按关键词
    ./docs/tm_kit/tools/tm_docs find --task "跨进程发请求收响应"
    ./docs/tm_kit/tools/tm_docs headers CommonFlowUtils.hpp   # 头文件反查
    ./docs/tm_kit/tools/tm_docs show tm_basic/09-transaction --section 易错点

文档版本：见 `docs/tm_kit/VERSIONS.json`。若与项目实际依赖的 tm_kit commit 不一致，
以源码为准并提醒我。
````

## 4. 版本对齐

`VERSIONS.json` 记录了文档校验时三个库的 commit：

```json
{
  "validated_at": "2026-10-10",
  "libraries": {
    "tm_infra":     { "commit": "f3432a9", ... },
    "tm_basic":     { "commit": "b254469", ... },
    "tm_transport": { "commit": "d6ddb0e", ... }
  }
}
```

**下游应该做的事**：在自己的构建配置里也记录所用的 tm_kit commit，与这份对不上时，agent 写的代码可能用了文档里有、但你的 tm_kit 版本里还没有的 API。这类错误不会在文档层面暴露，只会在编译时炸——所以值得在 CLAUDE.md 里显式提一句（上面那段结尾的提醒就是为此）。

## 5. 在上游改 API 之后

文档的行号引用会随源码漂移。上游动过 tm_infra / tm_basic / tm_transport 之后：

```bash
cd tm_kit_reference
python3 tools/stamp_versions.py          # 更新版本戳
python3 tools/validate_docs.py           # 看有没有引用失效
python3 tools/gen_agent_index.py         # 若改过 front-matter，重新生成索引
```

`validate_docs.py` 会检查：相对链接、front-matter 完整性、代码围栏配对、`file.hpp:line` 引用的文件是否存在、生成物是否同步、版本戳是否与各库 HEAD 一致。

建议在上游仓库加一条 CI（任选其一，装在哪取决于上游仓库能否访问到文档仓库）：

```yaml
# .github/workflows/docs.yml（放在 tm_kit_reference 仓库）
name: docs
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 tools/validate_docs.py --quick
      - run: python3 tools/gen_agent_index.py --check
```

`--quick` 跳过需要三个库在场的两项（源码引用、版本戳）。要跑全量，CI 里得把三个库也 checkout 到同级目录。

## 6. 本仓库的工具

| 工具 | 作用 |
|---|---|
| `tools/tm_docs` | 检索 CLI：`find` / `headers` / `show` / `list` / `index`。零依赖单文件 |
| `tools/gen_agent_index.py` | 从 front-matter 生成 `AGENT_INDEX.md` 与 `LOOKUP.md` |
| `tools/agent_index_header.md` | `AGENT_INDEX.md` 的手写部分（铁律、路由表）。**改这里，不要改生成物** |
| `tools/stamp_versions.py` | 更新 `VERSIONS.json`；`--check` 用于 CI |
| `tools/validate_docs.py` | 全量校验；退出码非零表示失败 |

三个脚本都只用 Python 3 标准库，无需安装任何东西。

## 7. 相关文档

- [AGENT_INDEX.md](AGENT_INDEX.md) —— agent 的入口（铁律 + 路由表）
- [README.md](README.md) —— 文档总览与全书索引
- [QUICK_START.md](QUICK_START.md) —— 从零写第一个 tm_kit 程序
- [PATTERNS.md](PATTERNS.md) —— 跨库模式与易错点
