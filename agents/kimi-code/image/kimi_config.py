#!/usr/bin/env python3
"""~/.kimi-code/config.toml 的托管：网关（providers.wonton）和 Kimi 开放平台
（providers.moonshot-cn）两个来源写同一份配置，谁在用 default_model 就指向谁，
优先级是网关 > 平台 key。密钥规则：网关的 key 只写变量名（api_key_env），
平台 key 是用户自己输入的登录态，照上游 login 流程的做法写进配置，文件 0600。

用法：
    kimi_config.py gateway-apply   # 读 WONTON_MODEL_BASE_URL / WONTON_MODEL_DEFAULT，写网关
    kimi_config.py gateway-clear   # 移除网关；平台 key 在时 default_model 指回平台
    kimi_config.py platform-set <api-key>   # 对平台验证 key，通过后写入（列模型选默认）
    kimi_config.py platform-clear  # 移除平台 key（预留给以后，登录流程暂不用）
"""
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 开放平台和平台模型前缀照上游 kimi-code 的 OPEN_PLATFORMS（moonshot-cn 档）：
# baseUrl 固定；allowedPrefixes 过滤出 Kimi 的模型。
PLATFORM_BASE_URL = "https://api.moonshot.cn/v1"
PLATFORM_PREFIX = "kimi-k"
GATEWAY_PROVIDER = "wonton"
GATEWAY_ALIAS = "wonton/default"
PLATFORM_PROVIDER = "moonshot-cn"

BEGIN, END = "# BEGIN WONTON", "# END WONTON"

# 只放行 Wonton MCP 这个服务器的工具：桥传进来的服务器名是 wonton，工具名前缀 mcp__wonton__，
# 其余工具照常按模式问。没有这段，Agent 调 Wonton 工具会和核心各出一张确认卡。
# 写法照上游文档的 [[permission.rules]]。
PERMISSION_TOML = (
    "[[permission.rules]]\n"
    'decision = "allow"\n'
    'pattern = "mcp__wonton__*"\n'
)


def home() -> Path:
    override = os.environ.get("KIMI_CODE_HOME", "").strip()
    return Path(override) if override else Path.home() / ".kimi-code"


def config_path() -> Path:
    return home() / "config.toml"


def write(text: str) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def toml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_str(value: str) -> str:
    """值里的换行按 TOML 基本字符串转义，别的字符原样。"""
    return toml_quote(value).replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def split_blocks(text: str) -> tuple[str | None, str | None, str]:
    """返回（网关块、平台块、其余原文）。块以标记行定界，其余内容逐字保留。"""
    gateway = platform = None
    rest: list[str] = []
    current: list[str] | None = None
    kind = ""
    for line in text.splitlines():
        if line.startswith(BEGIN):
            kind = line[len(BEGIN):].strip()
            current = [line]
            continue
        if line.startswith(END) and current is not None:
            block = "\n".join(current + [line]) + "\n"
            if kind == " GATEWAY":
                gateway = block
            elif kind == " PLATFORM":
                platform = block
            current = None
            continue
        if current is not None:
            current.append(line)
        elif not line.startswith("default_model ="):
            rest.append(line)
    return gateway, platform, "\n".join(rest).lstrip("\n")


def gateway_block(base_url: str, model: str) -> str:
    return (
        f"{BEGIN} GATEWAY\n"
        f"[providers.{GATEWAY_PROVIDER}]\n"
        f'type = "openai"\n'
        f"base_url = {toml_str(base_url)}\n"
        f'api_key_env = "WONTON_MODEL_API_KEY"\n'
        f"\n"
        f'[models.{toml_quote(GATEWAY_ALIAS)}]\n'
        f'provider = "{GATEWAY_PROVIDER}"\n'
        f"model = {toml_str(model)}\n"
        # 网关模型按 env 覆盖的同一默认给窗口（上游 DEFAULT_MAX_CONTEXT_SIZE），
        # 不写这行 kimi 的模型解析会判 unresolvable。
        f"max_context_size = 262144\n"
        f"{END} GATEWAY\n"
    )


def platform_block(api_key: str, models: list[str]) -> str:
    lines = [f"{BEGIN} PLATFORM", f"[providers.{PLATFORM_PROVIDER}]", 'type = "kimi"',
             f"base_url = {toml_str(PLATFORM_BASE_URL)}", f"api_key = {toml_str(api_key)}", ""]
    for model in models:
        alias = f"{PLATFORM_PROVIDER}/{model}"
        lines += [f"[models.{toml_quote(alias)}]", f'provider = "{PLATFORM_PROVIDER}"',
                  f"model = {toml_str(model)}", ""]
    lines.append(f"{END} PLATFORM")
    return "\n".join(lines) + "\n"


def assemble(gateway: str | None, platform: str | None) -> str:
    parts: list[str] = []
    if gateway:
        parts.append(f'default_model = {toml_quote(GATEWAY_ALIAS)}\n')
    elif platform:
        parts.append(f"default_model = {toml_quote(platform_default_model(platform))}\n")
    parts.append(PERMISSION_TOML)
    if gateway:
        parts.append(gateway)
    if platform:
        parts.append(platform)
    return "\n".join(parts)


def platform_default_model(platform_block_text: str) -> str:
    for line in platform_block_text.splitlines():
        if line.startswith("model = "):
            return line[len("model = "):].strip().strip('"')
    raise ValueError("平台块里没有模型")


def gateway_apply() -> None:
    base_url = os.environ.get("WONTON_MODEL_BASE_URL", "").strip()
    model = os.environ.get("WONTON_MODEL_DEFAULT", "").strip()
    if not base_url or not model:
        print("网关变量缺失：WONTON_MODEL_BASE_URL / WONTON_MODEL_DEFAULT 必须有值", file=sys.stderr)
        sys.exit(1)
    gateway, platform, _ = split_blocks(config_path().read_text(encoding="utf-8")
                                        if config_path().exists() else "")
    write(assemble(gateway_block(base_url, model), platform))


def gateway_clear() -> None:
    if not config_path().exists():
        return
    gateway, platform, _ = split_blocks(config_path().read_text(encoding="utf-8"))
    write(assemble(None, platform))


def platform_set(api_key: str) -> None:
    models = platform_models(api_key)
    if not models:
        print("平台账号下没有 Kimi 模型（kimi-k* 前缀），key 没有写入", file=sys.stderr)
        sys.exit(1)
    gateway, _platform, _ = split_blocks(config_path().read_text(encoding="utf-8")
                                         if config_path().exists() else "")
    write(assemble(gateway, platform_block(api_key, models)))
    default = platform_default_model(platform_block(api_key, models))
    print(f"Kimi 开放平台 key 已保存，默认模型 {PLATFORM_PROVIDER}/{default}")


def platform_clear() -> None:
    if not config_path().exists():
        return
    gateway, _platform, _ = split_blocks(config_path().read_text(encoding="utf-8"))
    write(assemble(gateway, None))


def platform_models(api_key: str) -> list[str]:
    """照上游 login 的做法先用 key 列模型验证，再取 kimi-k* 前缀的模型。"""
    request = urllib.request.Request(
        f"{PLATFORM_BASE_URL.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = str(json.load(error))[:200]
        except Exception:
            detail = error.reason
        print(f"平台拒绝了这把 key（HTTP {error.code}）：{detail}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"连不上开放平台 {PLATFORM_BASE_URL}：{error}", file=sys.stderr)
        sys.exit(1)
    data = payload.get("data") if isinstance(payload, dict) else None
    ids = [item.get("id") for item in data if isinstance(item, dict)]
    return [str(model) for model in ids if isinstance(model, str) and model.startswith(PLATFORM_PREFIX)]


def main() -> None:
    args = sys.argv[1:]
    if args == ["gateway-apply"]:
        gateway_apply()
    elif args == ["gateway-clear"]:
        gateway_clear()
    elif len(args) == 2 and args[0] == "platform-set":
        platform_set(args[1])
    elif args == ["platform-clear"]:
        platform_clear()
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
