#!/usr/bin/env python3
"""Wonton 的长度规矩：源码文件超过 800 行代码警告、超过 2000 行失败，函数 ≤ 100 行。超了逐条列出并退出 1。

文件只数代码行：空行和去掉首尾空白后以 `#` 开头的行不算（文档字符串算代码）。800 行的警告是该按职责拆的信号；
不许为了缩短行数写难懂的代码，删注释、把多行挤成一行、缩短有意义的名字都不行。
扫描仓库里所有 .py 和入口脚本 wonton-agent；CI 和发布前都先跑它。
"""
import ast
import os
import sys
from pathlib import Path

WARN_FILE_LINES = 800
MAX_FILE_LINES = 2000
MAX_FUNCTION_LINES = 100
ROOT = Path(__file__).resolve().parent.parent


def targets() -> list[Path]:
    files = [path for path in sorted(ROOT.rglob("*.py"))
             if not {".git", "__pycache__"} & set(path.parts)]
    return files + [ROOT / "wonton-agent"]


def code_lines(text: str) -> int:
    stripped = (line.strip() for line in text.splitlines())
    return sum(1 for line in stripped if line and not line.startswith("#"))


def warn(path: Path, line_count: int) -> None:
    message = (f"{path} 有 {line_count} 行代码（不算空行和注释），"
               f"超过 {WARN_FILE_LINES}，按职责拆")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning file={path}::{message}")
    else:
        print(f"警告：{message}")


def check_file(path: Path) -> list[str]:
    text = path.read_text()
    problems = []
    line_count = code_lines(text)
    if line_count > MAX_FILE_LINES:
        problems.append(f"{path.relative_to(ROOT)}：{line_count} 行代码（不算空行和注释，上限 {MAX_FILE_LINES}）")
    elif line_count > WARN_FILE_LINES:
        warn(path.relative_to(ROOT.parent), line_count)
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = node.end_lineno - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            problems.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}：{length} 行"
                            f"（上限 {MAX_FUNCTION_LINES}）")
    return problems


def main() -> int:
    problems = [problem for path in targets() for problem in check_file(path)]
    for problem in problems:
        print(problem)
    if problems:
        print(f"共 {len(problems)} 处超长")
        return 1
    print("文件和函数长度都在上限内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
