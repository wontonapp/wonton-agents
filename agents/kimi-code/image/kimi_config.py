#!/usr/bin/env python3
"""托管模型来源，保留订阅 OAuth、工具和权限；不恢复外部 API 路由。"""
import json
import os
import stat
import sys
import tomllib
from datetime import date, datetime, time
from pathlib import Path

NATIVE_PROVIDER = "managed:kimi-code"
GATEWAY_PROVIDER = "magpie"
GATEWAY_ALIAS = "magpie/default"


def home() -> Path:
    override = os.environ.get("KIMI_CODE_HOME", "").strip()
    return Path(override) if override else Path.home() / ".kimi-code"


def config_path() -> Path:
    return home() / "config.toml"


def toml_value(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value).lower()
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_value(key)} = {toml_value(item)}"
                                 for key, item in value.items()) + " }"
    raise ValueError(f"Unsupported TOML value: {type(value).__name__}")


def write(data: dict) -> None:
    # Inline tables preserve nested tool/permission values without a TOML writer dependency.
    text = "".join(f"{toml_value(key)} = {toml_value(value)}\n" for key, value in data.items())
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load() -> dict:
    try:
        with config_path().open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as error:
        sys.exit(f"Kimi 配置不是合法 TOML：{error}")


def subscription_config(data: dict) -> tuple[dict, dict]:
    provider = data.get("providers", {}).get(NATIVE_PROVIDER, {})
    # A provider name alone is not subscription authentication.
    if not provider.get("oauth"):
        return {}, {}
    provider = dict(provider)
    provider.pop("api_key", None)
    provider.pop("api_key_env", None)
    provider.pop("env", None)
    models = {alias: model for alias, model in data.get("models", {}).items()
              if model.get("provider") == NATIVE_PROVIDER}
    return {NATIVE_PROVIDER: provider}, models


def configure(gateway: bool) -> None:
    if not gateway and os.environ.get("WONTON_AGENT_MODEL_SOURCE") != "official":
        sys.exit("模型网关未就绪：只有明确选择官方订阅后才能清除网关配置")
    if gateway:
        required = ("WONTON_MODEL_BASE_URL", "WONTON_MODEL_API_KEY", "WONTON_MODEL_DEFAULT")
        missing = [key for key in required if not os.environ.get(key, "").strip()]
        if missing:
            sys.exit("模型网关未就绪：缺少 " + " / ".join(missing))
    data = load()
    providers, models = ({}, {}) if gateway else subscription_config(data)
    if gateway:
        providers[GATEWAY_PROVIDER] = {
            "type": "openai",
            "base_url": os.environ["WONTON_MODEL_BASE_URL"].strip(),
            "api_key_env": "WONTON_MODEL_API_KEY",
        }
        models[GATEWAY_ALIAS] = {
            "provider": GATEWAY_PROVIDER,
            "model": os.environ["WONTON_MODEL_DEFAULT"].strip(),
            "display_name": "magpie",
            "max_context_size": 262144,
        }
        selected = GATEWAY_ALIAS
        data["default_provider"] = GATEWAY_PROVIDER
    else:
        if not providers or not models:
            sys.exit("Kimi 官方订阅未就绪：请重新完成 Kimi 账号设备码登录")
        selected = data.get("default_model")
        if selected not in models:
            selected = next(iter(models))
        data["default_provider"] = NATIVE_PROVIDER
    data["providers"] = providers
    data["models"] = models
    data["default_model"] = selected
    # Upstream's lone default_model pins all Agent/AgentSwarm roles, without a selectable pool.
    data["secondary_model"] = {"default_model": selected}
    permission = data.setdefault("permission", {})
    rules = permission.setdefault("rules", [])
    rule = {"decision": "allow", "pattern": "mcp__wonton__*"}
    if rule not in rules:
        rules.append(rule)
    write(data)


def gateway_apply() -> None:
    configure(True)


def gateway_clear() -> None:
    configure(False)
