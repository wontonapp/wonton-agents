"""Read and write Qwen Code user settings, preserving unrelated tool settings."""
import json
import os
import sys
from pathlib import Path

SETTINGS = Path(os.path.expanduser("~/.qwen/settings.json"))


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




def ensure(data: dict, *path: str) -> dict:
    """按路径走到最里层的对象，缺的段补成 {}。"""
    node = data
    for key in path:
        child = node.setdefault(key, {})
        if not isinstance(child, dict):
            sys.exit(f"{SETTINGS} 的 {'.'.join(path)} 里有不是对象的段，先手工修好再启动")
        node = child
    return node
