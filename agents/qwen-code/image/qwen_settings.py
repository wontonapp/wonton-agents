"""改写 qwen-code 的用户设置 ~/.qwen/settings.json：网关钩子和登录脚本共用。
只动自己的键，别的键和用户自己写的值原样留着；写回 0600（qwen-code 自己也把模型选择
持久化在这个文件里）。"""
import json
import os
import sys
from pathlib import Path

SETTINGS = Path(os.path.expanduser("~/.qwen/settings.json"))
# 网关 apply 前这些键的原值（null 表示原来没有），clear 时按它还原。
BACKUP = Path(os.path.expanduser("~/.qwen/wonton-gateway.json"))
# 网关写进 modelProviders 的条目带这个 description：既是说明也是识别标记，
# clear 和下次 apply 靠它只动自己的条目，不碰用户自己的。
GATEWAY_ENTRY_MARK = "Wonton model gateway"


def load() -> dict:
    try:
        text = SETTINGS.read_text()
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(text)
    except ValueError as error:
        sys.exit(f"{SETTINGS} 不是合法 JSON（{error}），先手工修好再启动")
    if not isinstance(data, dict):
        sys.exit(f"{SETTINGS} 顶层不是对象，先手工修好再启动")
    return data


def save(data: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    SETTINGS.chmod(0o600)


def at(data: dict, *path: str):
    """按路径取嵌套值，缺哪段都算没有（None）；中间的段存在但不是对象时报错。"""
    node = data
    for key in path:
        if node is None:
            return None
        if not isinstance(node, dict):
            sys.exit(f"{SETTINGS} 的 {'.'.join(path)} 里有不是对象的段，先手工修好再启动")
        node = node.get(key)
    return node


def ensure(data: dict, *path: str) -> dict:
    """按路径走到最里层的对象，缺的段补成 {}。"""
    node = data
    for key in path:
        child = node.setdefault(key, {})
        if not isinstance(child, dict):
            sys.exit(f"{SETTINGS} 的 {'.'.join(path)} 里有不是对象的段，先手工修好再启动")
        node = child
    return node


def read_backup() -> dict | None:
    try:
        return json.loads(BACKUP.read_text())
    except FileNotFoundError:
        return None
    except ValueError:
        # 备份坏了也要能往下走：按“原来没有”处理，别把用户卡在启动失败上。
        return {}


def write_backup(values: dict) -> None:
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps(values, ensure_ascii=False) + "\n")
    BACKUP.chmod(0o600)
