"""Claude Code 用户设置；只改模型路由键，保留工具和权限设置。"""
import json
import os
import sys
from pathlib import Path

SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
# 旧版备份只删除，不能恢复外部模型路由。
BACKUP = Path(os.path.expanduser("~/.claude/wonton-gateway.json"))

MODEL_ENV = (
    "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_AUTO_MODE_MODEL",
)


def gateway_env() -> dict[str, str]:
    required = ("WONTON_MODEL_ANTHROPIC_BASE_URL", "WONTON_MODEL_API_KEY", "WONTON_MODEL_DEFAULT")
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        sys.exit("模型网关未就绪：缺少 " + " / ".join(missing))
    model = os.environ["WONTON_MODEL_DEFAULT"].strip()
    return {"ANTHROPIC_BASE_URL": os.environ["WONTON_MODEL_ANTHROPIC_BASE_URL"].strip(),
            "ANTHROPIC_AUTH_TOKEN": os.environ["WONTON_MODEL_API_KEY"].strip(),
            **{key: model for key in MODEL_ENV}}


def route_env_key(key: str) -> bool:
    return key.startswith("ANTHROPIC_") or key.startswith("CLAUDE_CODE_USE_") or key in (
        "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_AUTO_MODE_MODEL",
        "CLAUDE_CONFIG_DIR",
    )


def clean_process_env() -> None:
    for key in list(os.environ):
        if route_env_key(key):
            del os.environ[key]


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


def remove_model_routes(data: dict) -> None:
    env = env_of(data)
    for key in list(env):
        if route_env_key(key):
            del env[key]
    for key in ("apiKeyHelper", "model", "availableModels", "modelOverrides", "advisorModel",
                "forceLoginMethod", "forceLoginGatewayUrl", "forceLoginOrgUUID"):
        data.pop(key, None)
    BACKUP.unlink(missing_ok=True)
    (SETTINGS.parent / "api-key").unlink(missing_ok=True)
    for path, keys in (
        (SETTINGS.parent.parent / ".claude.json", ("primaryApiKey", "customApiKeyResponses")),
        (SETTINGS.parent / ".credentials.json", ("anthropicApiKey",)),
    ):
        try:
            credentials = json.loads(path.read_text())
        except FileNotFoundError:
            continue
        except ValueError as error:
            sys.exit(f"{path} 不是合法 JSON：{error}")
        if not isinstance(credentials, dict):
            sys.exit(f"{path} 顶层不是对象")
        changed = False
        for key in keys:
            if key in credentials:
                del credentials[key]
                changed = True
        if changed:
            path.write_text(json.dumps(credentials, indent=2, ensure_ascii=False) + "\n")
            path.chmod(0o600)
