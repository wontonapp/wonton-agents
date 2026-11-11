"""改写 Claude Code 的用户设置 ~/.claude/settings.json：网关钩子和登录脚本共用。
只动自己的键，别的键和用户自己写的值原样留着；写回时 0600（网关密钥可能落到这里）。"""
import json
import os
import sys
from pathlib import Path

SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
# 网关 apply 前这些键的原值（null 表示原来没有），clear 时按它还原。
BACKUP = Path(os.path.expanduser("~/.claude/wonton-gateway.json"))
API_KEY_HELPER = "/usr/local/lib/wonton-agent/api-key"


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


def env_of(data: dict) -> dict:
    env = data.setdefault("env", {})
    if not isinstance(env, dict):
        sys.exit(f"{SETTINGS} 的 env 不是对象，先手工修好再启动")
    return env


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
