#!/usr/bin/env python3
"""发布 tag 的校验：`<id>/v<版本>` 或 `base/v<版本>`，版本要和仓库里的版本号一致。

输出 kind / id / version 到 GITHUB_OUTPUT；写错了退出 1，发错 tag 不能悄悄发出别的版本。
"""

import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ref = sys.argv[1]
    name, _, version = ref.rpartition("/v")
    if not name or not version:
        sys.exit(f"tag 要写成 <id>/v<版本> 或 base/v<版本>：{ref}")
    if name == "base":
        kind, expected = "base", (ROOT / "base/VERSION").read_text().strip()
    else:
        if "/" in name:
            sys.exit(f"插件 tag 只能有一段：{ref}")
        kind = "agent"
        manifest = ROOT / "agents" / name / "agent.yaml"
        if not manifest.is_file():
            sys.exit(f"没有 {manifest.relative_to(ROOT)}")
        found = re.search(r"^version:\s*['\"]?([^'\"\s]+)", manifest.read_text(encoding="utf-8"), re.M)
        if not found:
            sys.exit(f"{manifest.relative_to(ROOT)} 没有 version")
        expected = found.group(1)
    if expected != version:
        sys.exit(f"tag 的版本 {version} 和仓库里的 {expected} 不同")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"kind={kind}\nid={name}\nversion={version}\n")


if __name__ == "__main__":
    main()
