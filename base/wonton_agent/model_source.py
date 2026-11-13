"""Bot 的模型来源：只记录主人成功选择的登录方式，不从上游凭据猜模式。"""
import os
from pathlib import Path

from . import config


class ModelNotReady(RuntimeError):
    """模型不能启动，但登录控制通道仍可用。"""


def choice_path() -> Path:
    return config.AGENT_HOME / ".wonton-model-source"


def official_login(settings: dict) -> str | None:
    try:
        selected = choice_path().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if any(item["id"] == selected and item.get("model_source") == "official"
           for item in settings.get("login", [])):
        return selected
    raise ModelNotReady("模型来源未就绪：保存的官方登录方式不在配置中，请重新选择官方订阅或 magpie")


def select(section: dict) -> None:
    source = section.get("model_source")
    if source is None:
        return
    path = choice_path()
    if source == "gateway":
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".new")
    temporary.write_text(section["id"] + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)
