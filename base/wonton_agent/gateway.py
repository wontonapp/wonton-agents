"""网关是默认模型来源；只有主人成功选择官方订阅才调 clear。
未就绪不改配置、不启动上游 Agent，登录通道可继续使用。
"""
import os
import subprocess

from . import die, log, model_source

GATEWAY_ENV = ("WONTON_MODEL_BASE_URL", "WONTON_MODEL_API_KEY", "WONTON_MODEL_DEFAULT")


def source_env(config: dict) -> dict[str, str]:
    selected = model_source.official_login(config)
    return {"WONTON_AGENT_MODEL_SOURCE": "official" if selected else "gateway",
            "WONTON_AGENT_LOGIN_ID": selected or ""}


def require_gateway(config: dict) -> None:
    section = config.get("gateway", {})
    required = (*GATEWAY_ENV, *section.get("required_env", []), *section.get("env", {}).values())
    missing = sorted({key for key in required if not os.environ.get(key, "").strip()})
    if missing:
        raise model_source.ModelNotReady(
            f"magpie 模型网关未就绪：缺少 {'、'.join(missing)}；请在模型设置中检查网关，不会改连官方或其他服务")


def apply_gateway(config: dict) -> None:
    section = config.get("gateway")
    if not section:
        return
    env = source_env(config)
    action = "clear" if env["WONTON_AGENT_MODEL_SOURCE"] == "official" else "apply"
    hook = section["hook"]
    if not os.access(hook, os.X_OK):
        die(f"网关钩子 {hook} 不存在或不可执行：子镜像要 COPY 自己的钩子到这里，或在 [gateway] 里改 hook")
    if action == "apply":
        require_gateway(config)
    log(f"模型来源 {env['WONTON_AGENT_MODEL_SOURCE']}：调 {hook} {action}")
    result = subprocess.run([hook, action], stdin=subprocess.DEVNULL, env={**os.environ, **env})
    if result.returncode != 0:
        raise RuntimeError(f"网关钩子 {hook} {action} 失败（退出码 {result.returncode}），看上面日志")


def acp_env(config: dict) -> dict[str, str]:
    """官方模式不注入网关映射；网关模式缺变量时拒绝启动模型。"""
    section = config.get("gateway")
    if not section or model_source.official_login(config):
        return {}
    require_gateway(config)
    return {target: os.environ[source] for target, source in section.get("env", {}).items()}
