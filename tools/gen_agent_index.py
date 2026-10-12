#!/usr/bin/env python3
"""从各篇的 YAML front-matter 生成 AGENT_INDEX.md。

AGENT_INDEX.md 是给下游项目的 agent 常驻加载的入口文件：版本戳 + 手写铁律 +
自动生成的路由表 / 头文件索引 / 关键词索引。

手写部分在 tools/agent_index_header.md，本脚本只负责拼装它与其后的生成部分。
**不要直接编辑 AGENT_INDEX.md。**

用法：
    python3 tools/gen_agent_index.py            # 写入 AGENT_INDEX.md
    python3 tools/gen_agent_index.py --check    # 只检查是否为最新（CI 用）
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

DOCS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DOCS_ROOT, "AGENT_INDEX.md")
LOOKUP_OUT = os.path.join(DOCS_ROOT, "LOOKUP.md")
HEADER = os.path.join(DOCS_ROOT, "tools", "agent_index_header.md")
VERSIONS = os.path.join(DOCS_ROOT, "VERSIONS.json")

SKIP_FILES = {"README.md", "AGENT_INDEX.md", "LOOKUP.md", "GLOSSARY.md",
              "CONTRIBUTING-DOCS.md", "THIRD_PARTY.md", "PATTERNS.md",
              "QUICK_START.md", "EXAMPLES_MAP.md", "DOWNSTREAM.md"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_front_matter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = FM_RE.match(text)
    if not m:
        return {}
    fm = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        elif val == "":
            # 可能是块状列表；收集后续的 "  - item" 行
            items = []
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]).strip())
                i += 1
            fm[key] = items if items else ""
        else:
            fm[key] = val
    return fm


def collect():
    """返回 [(relpath, front_matter)]，按 library 与文件名排序。"""
    items = []
    for dirpath, dirnames, filenames in os.walk(DOCS_ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("tools", ".git")]
        for f in sorted(filenames):
            if not f.endswith(".md") or f in SKIP_FILES:
                continue
            p = os.path.join(dirpath, f)
            fm = parse_front_matter(p)
            if fm is None:
                print(f"gen_agent_index: {p} 缺 front-matter", file=sys.stderr)
                return None
            rel = os.path.relpath(p, DOCS_ROOT)
            items.append((rel, fm))
    order = {"tm_infra": 0, "tm_basic": 1, "tm_transport": 2, "meta": 3}
    items.sort(key=lambda x: (order.get(x[1].get("library", "meta"), 9), x[0]))
    return items


def version_block():
    if not os.path.isfile(VERSIONS):
        return "> ⚠️ 缺 VERSIONS.json —— 跑 `python3 tools/stamp_versions.py` 生成。\n"
    v = json.load(open(VERSIONS, encoding="utf-8"))
    libs = v.get("libraries", {})
    docs = v.get("docs", {})
    out = [f"> **文档校验版本**：{v.get('validated_at','?')}"
           f" — {docs.get('files','?')} 篇 / {docs.get('lines','?')} 行\n>\n"]
    out.append("> | 库 | commit | 日期 |\n> |---|---|---|\n")
    for name in ("tm_infra", "tm_basic", "tm_transport"):
        info = libs.get(name, {})
        out.append(f"> | `{name}` | `{info.get('commit','?')}` | {info.get('commit_date','?')} |\n")
    out.append(">\n> 下游若 pin 的 tm_kit 版本与此不同，文档描述的 API 可能已经变了。\n"
               "> 核对方法：`python3 tools/stamp_versions.py --check`（需三个库在同一 workspace 下）。\n")
    return "".join(out)


def gen_chapters(items):
    out = ["\n## 全部章节\n\n",
           "| 章节 | 主题 |\n|---|---|\n"]
    for rel, fm in items:
        title = fm.get("title", rel)
        out.append(f"| [`{rel}`]({rel}) | {title} |\n")
    return "".join(out)


def gen_headers(items):
    """头文件 basename → 文档。同名头文件可能出现在多个库，都列出来。"""
    idx = defaultdict(list)
    for rel, fm in items:
        hs = fm.get("headers", [])
        if isinstance(hs, str):
            hs = [hs]
        for h in hs:
            base = os.path.basename(h.strip())
            if base:
                idx[base].append(rel)
    out = ["\n## 按头文件查\n\n",
           "拿到一个 `#include <tm_kit/...>` 想查文档时用这张表。\n\n",
           "| 头文件 | 文档 |\n|---|---|\n"]
    for base in sorted(idx):
        out.append(f"| `{base}` | {'、'.join(f'[{d}]({d})' for d in sorted(set(idx[base])))} |\n")
    return "".join(out)


def gen_keywords(items):
    """关键词 → 文档。同一个关键词命中多篇时全部列出（按相关性排序：标题命中的优先）。"""
    idx = defaultdict(list)
    for rel, fm in items:
        kws = fm.get("keywords", [])
        if isinstance(kws, str):
            kws = [kws]
        title = str(fm.get("title", ""))
        for k in kws:
            k = k.strip()
            if k:
                idx[k].append((0 if k in title else 1, rel))
    out = ["\n## 关键词索引\n\n",
           "`tools/tm_docs find <关键词>` 的等价物。命中多篇时按篇名相关性排序。\n\n"]
    for k in sorted(idx, key=lambda s: s.lower()):
        rels = [r for _, r in sorted(set(idx[k]))]
        links = "、".join(f"[{os.path.basename(r)}]({r})" for r in rels)
        out.append(f"- **{k}** — {links}\n")
    return "".join(out)


def build():
    """返回 (agent_index, lookup)。常驻文件保持小；两张检索表另存，供 grep / CLI 用。"""
    items = collect()
    if items is None:
        return None, None
    with open(HEADER, encoding="utf-8") as fh:
        header = fh.read()

    # 占位符由文档实际规模填充，避免手写部分写死后随文档增删而失真。
    # 直接数文件，不要用 len(items)+len(SKIP_FILES) 之类的算术——SKIP_FILES
    # 与目录内容会各自演化，算术迟早对不上。
    doc_count = line_count = 0
    for dirpath, dirnames, filenames in os.walk(DOCS_ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("tools", ".git")]
        for f in filenames:
            if f.endswith(".md"):
                doc_count += 1
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    line_count += sum(1 for _ in fh)
    header = (header.replace("{{DOC_COUNT}}", str(doc_count))
                    .replace("{{LINE_COUNT}}", f"{line_count:,}"))
    banner = ("<!-- 本文件由 tools/gen_agent_index.py 生成，请勿直接编辑。\n"
              "     手写内容改 tools/agent_index_header.md，然后重跑生成脚本。 -->\n\n")

    index = (banner + header.rstrip() + "\n\n" + version_block()
             + gen_chapters(items)
             + "\n> 章节的文件名含序号，同库内按序排列即推荐阅读顺序。\n"
             + "\n## 按头文件 / 关键词查\n\n"
             + "这两张表太大，不放进常驻文件。它们在本仓库的 `LOOKUP.md` 里，"
               "**用 grep 或 `tools/tm_docs` 精确命中单行，不必整篇读**：\n\n"
             + "```bash\n"
             + "./tools/tm_docs headers CommonFlowUtils.hpp\n"
             + "./tools/tm_docs find \"事务 订阅\"\n"
             + "grep -n \"CommonFlowUtils.hpp\" LOOKUP.md\n"
             + "```\n"
             + "\n---\n\n"
             + "*本文件由 `tools/gen_agent_index.py` 生成。手写部分改 "
               "`tools/agent_index_header.md`，改动会同时反映到两个输出文件。*\n")

    lookup = ("# 查找表 — 头文件 / 关键词 → 文档\n\n"
              "本文件由 `tools/gen_agent_index.py` 从各篇 front-matter 自动生成。"
              "**它不是给人通读的**，请用 grep 或 `tools/tm_docs` 精确命中。\n"
              + gen_headers(items) + gen_keywords(items)
              + "\n---\n\n*重新生成：`python3 tools/gen_agent_index.py`*\n")
    return index, lookup


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只检查是否为最新，不写文件")
    args = ap.parse_args()

    index, lookup = build()
    if index is None:
        return 2

    if args.check:
        stale = []
        for path, content in ((OUT, index), (LOOKUP_OUT, lookup)):
            if not os.path.isfile(path) or open(path, encoding="utf-8").read() != content:
                stale.append(os.path.basename(path))
        if stale:
            print(f"gen_agent_index: {' / '.join(stale)} 已过期，"
                  "请重跑 python3 tools/gen_agent_index.py", file=sys.stderr)
            return 1
        print("AGENT_INDEX.md / LOOKUP.md 都是最新的")
        return 0

    for path, content in ((OUT, index), (LOOKUP_OUT, lookup)):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"已生成 {os.path.relpath(path, DOCS_ROOT)}"
              f"  ({len(content):,} 字符, {content.count(chr(10)):,} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
