#!/usr/bin/env python3
"""校验 tm_kit_reference 的一致性。退出码 0 = 全部通过，1 = 有失败项。

检查项：
  1. 相对链接可解析
  2. 每篇 front-matter 四字段齐全（title / library / headers / keywords）
  3. 代码围栏配对
  4. 源码引用 `path/file.hpp:123` 的文件存在（需要三个库在同一 workspace 下，
     缺失时该项降级为 skipped 而非失败）
  5. AGENT_INDEX.md / LOOKUP.md 与 front-matter 同步
  6. VERSIONS.json 与各库 HEAD 一致（同样需要库在场）

用法：
    python3 tools/validate_docs.py            # 全部检查
    python3 tools/validate_docs.py --quick    # 跳过需要库在场的第 4、6 项
"""
import argparse
import json
import os
import re
import subprocess
import sys

DOCS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(DOCS_ROOT)
LIBS = ("tm_infra", "tm_basic", "tm_transport", "tm_examples")

SKIP_FM = {"CONTRIBUTING-DOCS.md", "AGENT_INDEX.md", "LOOKUP.md"}
# 已知的非仓库内引用：第三方头文件与文件名模式。改动需谨慎。
KNOWN_EXTERNAL = {
    "path/to/file.hpp",     # CONTRIBUTING-DOCS 里的格式示例
    "boost/algorithm/string.hpp",
    "mysql.h",
    "soci/soci.h",
    "simdjson.cpp",
    "_Piece.hpp",
    "_ClassPiece.hpp",
}

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)#]+?)(?:#[^)]*)?\)")
REF_RE = re.compile(r"`([A-Za-z0-9_./\-]+\.(?:hpp|cpp|h|cc))(?::(\d+))?`")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)



def parse_front_matter(text):
    """解析 YAML front-matter。同时支持行内列表 `k: [a, b]` 与块状列表：

        k:
          - a
          - b

    只认行内形式的话，块状列表会静默解析成空 —— 头文件索引与关键词索引会漏掉整篇。
    """
    m = FM_RE.match(text)
    if not m:
        return None
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
            items = []
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]).strip())
                i += 1
            fm[key] = items if items else ""
        else:
            fm[key] = val
    return fm


class Report:
    def __init__(self):
        self.failed = []
        self.warned = []
        self.skipped = []

    def fail(self, item, detail):
        self.failed.append((item, detail))

    def warn(self, item, detail):
        self.warned.append((item, detail))

    def skip(self, item, why):
        self.skipped.append((item, why))


def md_files():
    for dirpath, dirnames, filenames in os.walk(DOCS_ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("tools", ".git")]
        for f in sorted(filenames):
            if f.endswith(".md"):
                yield os.path.join(dirpath, f)


def check_links(rep):
    n = 0
    for path in md_files():
        in_fence = False
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # 去掉行内 code span，避免把 C++ lambda 签名误判成链接
            stripped = re.sub(r"`[^`]*`", "", line)
            for m in LINK_RE.finditer(stripped):
                target = m.group(2).strip()
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                n += 1
                resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
                if not (os.path.isfile(resolved) or os.path.isdir(resolved)):
                    rep.fail("链接", f"{os.path.relpath(path, DOCS_ROOT)}:{i} → {target}")
                elif not os.path.abspath(resolved).startswith(DOCS_ROOT + os.sep):
                    # 本仓库要能独立发布（submodule）。指向仓库外的链接在
                    # workspace 里能解析，一旦独立 clone 就全断——必须拦下。
                    rep.fail("跨仓库链接",
                             f"{os.path.relpath(path, DOCS_ROOT)}:{i} → {target}"
                             f"（逃出文档仓库，独立发布后会断）")
    return n


def check_front_matter(rep):
    n = 0
    for path in md_files():
        if os.path.basename(path) in SKIP_FM:
            continue
        n += 1
        text = open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, DOCS_ROOT)
        if not text.startswith("---"):
            rep.fail("front-matter", f"{rel}: 缺 front-matter")
            continue
        fm = parse_front_matter(text)
        if fm is None:
            rep.fail("front-matter", f"{rel}: front-matter 无法解析")
            continue
        for key in ("title", "library"):
            if not fm.get(key):
                rep.fail("front-matter", f"{rel}: 缺 {key}")
        # headers / keywords 必须是**非空列表**。只查 "key 出现过" 会漏掉
        # 语法写错（如块状列表被解析器忽略）导致的空列表。
        # keywords 任何一篇都必须有（决定检索命中）。
        # headers 只对三个库的正文章节强制非空；meta 文档（README/GLOSSARY/…）
        # 不覆盖具体头文件，写成 `headers: []` 是合法的。
        required = ["keywords"] + ([] if fm.get("library") == "meta" else ["headers"])
        for key in required:
            v = fm.get(key)
            if not isinstance(v, list) or not v:
                rep.fail("front-matter",
                         f"{rel}: {key} 未解析出非空列表（实际: {v!r}）")
    return n


def check_fences(rep):
    for path in md_files():
        n = sum(1 for line in open(path, encoding="utf-8")
                if line.lstrip().startswith("```"))
        if n % 2:
            rep.fail("代码围栏", f"{os.path.relpath(path, DOCS_ROOT)}: {n} 个围栏，不配对")


def build_source_index():
    """basename → [相对路径]，用于源码引用解析。"""
    idx = {}
    for lib in LIBS:
        root = os.path.join(WORKSPACE, lib)
        if not os.path.isdir(root):
            return None
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith("builddir") and d not in ("build", "external", ".git")]
            for f in filenames:
                if f.endswith((".hpp", ".cpp", ".h", ".cc")):
                    rel = os.path.relpath(os.path.join(dirpath, f), WORKSPACE)
                    idx.setdefault(f, []).append(rel)
    return idx


def check_source_refs(rep, quick):
    if quick:
        rep.skip("源码引用", "--quick")
        return 0, 0
    idx = build_source_index()
    if idx is None:
        rep.skip("源码引用", "三个库不在同一 workspace 下")
        return 0, 0
    total = 0
    unresolved = 0
    for path in md_files():
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            for m in REF_RE.finditer(line):
                ref = m.group(1)
                if ref in KNOWN_EXTERNAL:
                    continue
                total += 1
                base = os.path.basename(ref)
                if base in idx:
                    continue
                unresolved += 1
                rep.fail("源码引用",
                         f"{os.path.relpath(path, DOCS_ROOT)}:{i} → {ref}")
    return total, unresolved


def check_generated(rep):
    for script in ("gen_agent_index.py",):
        r = subprocess.run([sys.executable, os.path.join(DOCS_ROOT, "tools", script), "--check"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            rep.fail("生成物同步", (r.stderr or r.stdout).strip())


def check_versions(rep, quick):
    if quick:
        rep.skip("版本戳", "--quick")
        return
    if not all(os.path.isdir(os.path.join(WORKSPACE, l, ".git"))
               for l in LIBS[:3]):
        rep.skip("版本戳", "三个库不在同一 workspace 下")
        return
    r = subprocess.run([sys.executable, os.path.join(DOCS_ROOT, "tools", "stamp_versions.py"),
                        "--check"], capture_output=True, text=True)
    if r.returncode != 0:
        rep.fail("版本戳", (r.stderr or r.stdout).strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="跳过需要三个库在场的检查（第 4、6 项）")
    args = ap.parse_args()

    rep = Report()
    links = check_links(rep)
    chapters = check_front_matter(rep)
    check_fences(rep)
    refs, _ = check_source_refs(rep, args.quick)
    check_generated(rep)
    check_versions(rep, args.quick)

    print(f"链接检查      : {links} 条")
    print(f"章节 front-matter: {chapters} 篇")
    if refs:
        print(f"源码引用      : {refs} 处")
    for item, why in rep.skipped:
        print(f"[跳过] {item}: {why}")

    if rep.warned:
        print(f"\n警告 {len(rep.warned)} 条：")
        for item, detail in rep.warned:
            print(f"  [{item}] {detail}")

    if rep.failed:
        print(f"\n失败 {len(rep.failed)} 条：")
        for item, detail in rep.failed:
            print(f"  [{item}] {detail}")
        print("\n校验未通过。")
        return 1

    print("\n校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
