#!/usr/bin/env python3
"""记录本套文档所校验的 tm_kit 各库版本到 VERSIONS.json。

上游源码变动后跑一次，然后重跑 validate_docs.py。

用法：
    python3 tools/stamp_versions.py            # 自动找同级目录下的三个库
    python3 tools/stamp_versions.py --check    # 只报告差异，不写文件（CI 用）

退出码：0 成功 / 1 与已有戳不一致（仅 --check）/ 2 环境问题
"""
import argparse
import json
import os
import subprocess
import sys

LIBS = ("tm_infra", "tm_basic", "tm_transport")
DOCS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(DOCS_ROOT)


def git(repo, *args):
    try:
        out = subprocess.run(
            ("git", "-C", repo) + args,
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if out.returncode != 0:
        return None, out.stderr.strip()
    return out.stdout.strip(), None


def count_headers(repo):
    n = 0
    for dirpath, dirnames, filenames in os.walk(os.path.join(repo, "tm_kit")):
        dirnames[:] = [d for d in dirnames if d not in ("builddir", "build", "external")]
        n += sum(1 for f in filenames if f.endswith(".hpp"))
    return n


def collect():
    versions = {}
    for lib in LIBS:
        repo = os.path.join(WORKSPACE, lib)
        if not os.path.isdir(os.path.join(repo, ".git")):
            return None, f"{lib}: 在 {repo} 找不到 git 仓库"
        sha, err = git(repo, "rev-parse", "--short", "HEAD")
        if err:
            return None, f"{lib}: {err}"
        date, err = git(repo, "log", "-1", "--format=%cd", "--date=short")
        if err:
            return None, f"{lib}: {err}"
        remote, _ = git(repo, "remote", "get-url", "origin")
        versions[lib] = {
            "repo": remote or "",
            "commit": sha,
            "commit_date": date,
            "headers": count_headers(repo),
        }
    return versions, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="只对比，不写文件；有差异则退出码 1")
    args = ap.parse_args()

    path = os.path.join(DOCS_ROOT, "VERSIONS.json")
    versions, err = collect()
    if err:
        print(f"stamp_versions: {err}", file=sys.stderr)
        return 2

    if args.check:
        if not os.path.isfile(path):
            print("stamp_versions: VERSIONS.json 不存在", file=sys.stderr)
            return 1
        old = json.load(open(path, encoding="utf-8")).get("libraries", {})
        drift = [lib for lib in LIBS
                 if old.get(lib, {}).get("commit") != versions[lib]["commit"]]
        if drift:
            print("版本戳已过期，以下库在上次校验后有新提交：", file=sys.stderr)
            for lib in drift:
                print(f"  {lib}: 文档记 {old.get(lib,{}).get('commit','?')}"
                      f" → 实际 {versions[lib]['commit']}", file=sys.stderr)
            print("\n请重跑 tools/stamp_versions.py 并复检文档。", file=sys.stderr)
            return 1
        print("版本戳与各库 HEAD 一致")
        return 0

    doc = {}
    if os.path.isfile(path):
        doc = json.load(open(path, encoding="utf-8"))
    doc["_comment"] = ("本套文档所校验的 tm_kit 各库版本。上游源码变动后，"
                       "用 tools/stamp_versions.py 更新，并重跑 tools/validate_docs.py。")
    doc["validated_at"] = max(v["commit_date"] for v in versions.values())
    doc["libraries"] = versions

    # 文档规模
    files = lines = 0
    for dirpath, dirnames, filenames in os.walk(DOCS_ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("tools", ".git")]
        for f in filenames:
            if f.endswith(".md"):
                files += 1
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    lines += sum(1 for _ in fh)
    doc["docs"] = {"files": files, "lines": lines}

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"已更新 {os.path.relpath(path, DOCS_ROOT)}")
    for lib in LIBS:
        print(f"  {lib:<14} {versions[lib]['commit']}  {versions[lib]['commit_date']}"
              f"  ({versions[lib]['headers']} 个头文件)")
    print(f"  文档           {files} 篇 / {lines} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
