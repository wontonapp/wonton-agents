#!/usr/bin/env python3
"""ACP 注册表的版本机器人：某家的注册表版本比 agent.toml 里新时，改版本和摘要并提 PR。

只看 agents/<id>/agent.yaml 写了 registry: <注册表条目 id> 的插件。npm 条目的摘要从 npm registry 的
dist.integrity 取；二进制条目用注册表给的 linux sha256。注册表只当“新版本在哪”，打包和冒烟仍按插件自己的规则。

用法：
  python3 .github/registry_bot.py                 # 读注册表，有更新就改文件、推分支、开 PR
  python3 .github/registry_bot.py --dry-run       # 只打印改动
  python3 .github/registry_bot.py --registry 文件 --dry-run   # 演练/测试用本地注册表
"""

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import urllib.parse
import urllib.request

REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"
PLATFORMS = {"amd64": "linux-x86_64", "arm64": "linux-aarch64"}


def read_registry(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as response:
            return json.load(response)
    return json.loads(Path(source).read_text(encoding="utf-8"))


def semver(value: str) -> tuple[int, ...]:
    """只用来比大小：取数字段，忽略预发布后缀（注册表里没有预发布版本）。"""
    return tuple(int(part) for part in re.findall(r"\d+", value.split("-")[0]))


def version_key(manifest: Path) -> str:
    found = re.search(r"^registry:\s*['\"]?([^'\"\s]+)", manifest.read_text(encoding="utf-8"), re.M)
    return found.group(1) if found else ""


def install_blocks(text: str) -> list[tuple[int, int]]:
    """每个 [[install]] 的行范围（含段头，到下一个段的段头前）。"""
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "[[install]]"]
    blocks = []
    for start in starts:
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if re.match(r"^\s*\[", lines[index]):
                end = index
                break
        blocks.append((start, end))
    return blocks


def block_key(block: str) -> str:
    found = re.search(r'^\s*(package|name)\s*=\s*"([^"]+)"', block, re.M)
    return found.group(2) if found else ""


def pick_block(parsed: dict, key: str, source: str) -> int:
    matches = [index for index, block in enumerate(parsed.get("install", []))
               if block.get("source") == source and
               (block.get("package") == key or block.get("name") == key)]
    if len(matches) != 1:
        raise SystemExit(f"[[install]] 里 source = {source} 且 package/name = {key} 的段有 {len(matches)} 个，要正好一个")
    return matches[0]


def set_key(lines: list[str], start: int, end: int, key: str, value: str) -> None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index in range(start, end):
        if pattern.match(lines[index]):
            indent = re.match(r"^\s*", lines[index]).group(0)
            newline = "\n" if lines[index].endswith("\n") else ""
            lines[index] = f'{indent}{key} = "{value}"{newline}'
            return
    # 没有这一项时加在段头后面。
    lines.insert(start + 1, f'{key} = "{value}"\n')


def new_versions(entry: dict, block: dict) -> dict[str, str]:
    """按注册表条目算要写的键值。"""
    values = {"version": entry["version"]}
    if "npx" in entry["distribution"]:
        package = entry["distribution"]["npx"]["package"]
        name, _, _ = package.rpartition("@")
        url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/{entry['version']}"
        with urllib.request.urlopen(url, timeout=60) as response:
            integrity = json.load(response)["dist"]["integrity"]
        values["integrity"] = integrity
        return values
    for arch, key in PLATFORMS.items():
        binary = entry["distribution"]["binary"].get(key)
        if not binary or not binary.get("sha256"):
            raise SystemExit(f"注册表条目 {entry['id']} 缺 {key} 的 sha256")
        values[f"url_{arch}"] = binary["archive"]
        values[f"sha256_{arch}"] = binary["sha256"]
    archive = entry["distribution"]["binary"][PLATFORMS["amd64"]]["archive"]
    values["format"] = "tgz" if archive.endswith((".tar.gz", ".tgz")) else "binary"
    return values


def locate(parsed: dict, entry: dict) -> tuple[int, str]:
    """找到注册表条目对应的 [[install]] 段：npm 按包名，二进制按 name 或 URL 里的条目 id。"""
    if "npx" in entry["distribution"]:
        package = entry["distribution"]["npx"]["package"].rpartition("@")[0]
        return pick_block(parsed, package, "npm"), package
    for index, block in enumerate(parsed.get("install", [])):
        if block.get("source") != "url":
            continue
        urls = " ".join(str(value) for key, value in block.items() if key.startswith("url_"))
        if block.get("name") == entry["id"] or f"/{entry['id']}/" in urls or f"/{entry['id']}-" in urls:
            return index, block["name"]
    raise SystemExit("[[install]] 里找不到指向注册表条目的 url 段")


def rewrite(manifest: Path, entry: dict) -> str:
    text = manifest.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    index, _ = locate(parsed, entry)
    lines = text.splitlines(keepends=True)
    start, end = install_blocks(text)[index]
    values = new_versions(entry, parsed["install"][index])
    for name, value in values.items():
        set_key(lines, start, end, name, value)
    updated = "".join(lines)
    # ACP 命令里的工具版本目录跟着改（base 按 <名字>/<版本>/ 装到数据卷）。
    tool = parsed["install"][index]["name"]
    updated = re.sub(rf"(/tools/{re.escape(tool)}/)[^/\"']+", rf"\g<1>{entry['version']}", updated)
    # 改完要还能解析，且版本真的变了。
    after = tomllib.loads(updated)["install"][index]
    if after["version"] != entry["version"]:
        raise SystemExit("改写后版本没变")
    return updated


def rfc_versions(entry: dict) -> str:
    if "npx" in entry["distribution"]:
        return f"npm `{entry['distribution']['npx']['package']}`（dist.integrity 已写进 agent.toml）"
    return "\n".join(f"- {platform}: {entry['distribution']['binary'][key]['archive']} "
                     f"（sha256 {entry['distribution']['binary'][key]['sha256']}）"
                     for platform, key in PLATFORMS.items())


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, capture_output=True, **kwargs)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(command)} 失败：{result.stderr.strip()}")
    return result


def open_pr(agent: str, entry: dict, manifest: Path, old: str, new: str) -> None:
    branch = f"chore/registry-{agent}-{new}"
    run(["git", "checkout", "-B", branch])
    run(["git", "add", str(manifest.relative_to(ROOT))])
    run(["git", "commit", "-m", f"chore({agent}): 升级 {entry['name']} 到 {new}"])
    run(["git", "push", "--force-with-lease", "origin", branch])
    body = f"""- 改了什么：`{manifest.relative_to(ROOT)}` 的版本 {old} → {new}，摘要按注册表（npm 条目取 dist.integrity）更新。
- 为什么：ACP 注册表发布了 {entry['name']} {new}。
- 来源：{REGISTRY_URL}（条目 `{entry['id']}`）
{rfc_versions(entry)}

冒烟通过后合并；发布按 `<id>/v<版本>` 打 tag。
"""
    with open(os.environ["RUNNER_TEMP"] + f"/pr-{agent}.md", "w", encoding="utf-8") as stream:
        stream.write(body)
    run(["gh", "pr", "create", "--title", f"chore({agent}): 升级 {entry['name']} 到 {new}",
         "--body-file", os.environ["RUNNER_TEMP"] + f"/pr-{agent}.md", "--base", "main"])
    run(["git", "checkout", "main"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=REGISTRY_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    registry = read_registry(args.registry)
    entries = {entry["id"]: entry for entry in registry["agents"]}
    updated = 0
    for manifest in sorted(AGENTS.glob("*/agent.yaml")):
        agent = manifest.parent.name
        if args.only and agent not in args.only:
            continue
        entry_id = version_key(manifest)
        if not entry_id:
            continue
        entry = entries.get(entry_id)
        if entry is None:
            print(f"{agent}: 注册表里没有 {entry_id}，跳过", file=sys.stderr)
            continue
        toml_path = manifest.parent / "image" / "agent.toml"
        parsed = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        current = parsed["install"][locate(parsed, entry)[0]]["version"]
        if semver(entry["version"]) <= semver(current):
            continue
        before = toml_path.read_text(encoding="utf-8")
        after = rewrite(toml_path, entry)
        print(f"{agent}: {current} → {entry['version']}")
        if args.dry_run:
            sys.stdout.writelines(difflib.unified_diff(before.splitlines(keepends=True),
                                                       after.splitlines(keepends=True),
                                                       f"a/{toml_path.relative_to(ROOT)}",
                                                       f"b/{toml_path.relative_to(ROOT)}"))
            continue
        toml_path.write_text(after, encoding="utf-8")
        open_pr(agent, entry, toml_path, current, entry["version"])
        updated += 1
    if not updated and not args.dry_run:
        print("没有要升级的版本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
