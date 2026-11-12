#!/usr/bin/env python3
"""把 agents/<id>/agent.yaml 和 template/ 合成 agents/<id>/docker-compose.yml。

字段缺失、写错、多余都报错退出，不猜不兜底；生成结果提交进仓库，CI 用 --check 验证没有过期。

    python3 gen/gen.py [--check] [agents/<id> …]    # 不给目录就是 agents/ 下全部

发版时 publish.sh 把 compose 里自身镜像的 image 行改写成 <仓库>:<版本>@sha256:<摘要>，提交只挂在 tag 上；
compose 里已有和清单版本一致的摘要时 gen 原样带上（agent 和 web 引用同一个镜像），--check 才能过。
版本一换旧摘要作废：生成不带摘要的新标签，等下一次发布再写。

agent.yaml 的字段（例子见 agents/echo/agent.yaml）：

    必填  id version title description about release_notes license notices homepage acp_mode memory
    可选  tags acp_topic_mode env webui login permissions

webui 只支持 true：登录网页端口由模板定死 8080，agent.toml 的 [web] 也配 8080。
依赖 PyYAML（MIT）：python3 -m pip install pyyaml，或系统包 python3-yaml。
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # 没装就说清装法，不静默换实现
    sys.exit("gen 需要 PyYAML（MIT）：python3 -m pip install pyyaml，或系统包 python3-yaml")

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "template"
COMPOSE_NAME = "docker-compose.yml"

REQUIRED = ("id", "version", "title", "description", "about", "release_notes",
            "license", "notices", "homepage", "acp_mode", "memory")
OPTIONAL = ("tags", "acp_topic_mode", "env", "webui", "login", "permissions")

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)+$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
LOGIN_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HOLE = re.compile(r"@@([A-Z_]+)@@")
WHOLE_HOLE = re.compile(r"^\s*@@([A-Z_]+)@@\s*$")
# 裸写会变语义的标量：YAML 的布尔/空词、数字、指示符打头、结构性空白。有歧义就双引号。
BOOL_WORDS = {"y", "Y", "yes", "Yes", "YES", "n", "N", "no", "No", "NO",
              "true", "True", "TRUE", "false", "False", "FALSE",
              "on", "On", "ON", "off", "Off", "OFF", "null", "Null", "NULL", "~", ""}
NUM_RE = re.compile(r"^(?:[-+]?[0-9][0-9_]*|[-+]?[0-9]*\.[0-9_]+(?:[eE][-+]?[0-9]+)?"
                    r"|[-+]?0[xXoObB][0-9a-fA-F_]+|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$")
# 桥启动就校验 WONTON_ACP_MODE（清单 acp_mode 经 compose 注入桥），名单外的值桥直接退、插件装不上；
# 名单照抄主仓库桥 config.rs 里的 ALLOWED_MODES，桥改名单时同步这里。
ACP_MODES = ("default", "plan", "acceptEdits", "read-only", "auto")


def fail(message: str):
    sys.exit(f"gen: {message}")


def scalar(value, flow: bool = False) -> str:
    """YAML 标量文本：能裸写就裸写（和手写的 compose 一致），有歧义就双引号并转义。"""
    if isinstance(value, list):
        return "[" + ", ".join(scalar(item, True) for item in value) + "]"
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif value is None:
        text = "null"
    else:
        text = str(value)
    unsafe = (text in BOOL_WORDS or NUM_RE.match(text) or text != text.strip() or text == "-"
              or text[0] in "-?:,[]{}#&*!|>'\"%@`" or ": " in text or text.endswith(":")
              or " #" in text or (flow and re.search(r"[\[\]{},]", text)))
    if unsafe:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def flow_multilang(texts: dict) -> str:
    """单行的多语言映射，如 { zh: Claude Code, en: Claude Code }。"""
    inner = ", ".join(f"{lang}: {scalar(text, True)}" for lang, text in texts.items())
    return "{ " + inner + " }"


def block_multilang(key: str, texts: dict, pad: str = "  ") -> list[str]:
    """多行的多语言映射；带换行的值写成 | 字面量块。"""
    lines = [f"{pad}{key}:"]
    sub = pad + "  "
    for lang, text in texts.items():
        if "\n" in text:
            lines.append(f"{sub}{lang}: |")
            lines += [f"{sub}  {line}" if line else "" for line in text.rstrip("\n").split("\n")]
        else:
            lines.append(f"{sub}{lang}: {scalar(text)}")
    return lines


def env_lines(env: dict, pad: str = "      ") -> list[str]:
    return [f"{pad}{name}: {scalar(value)}" for name, value in env.items()]


def login_block(entries: list, pad: str = "    ") -> list[str]:
    lines = [f"{pad}login:"]
    for entry in entries:
        lines.append(f"{pad}  - id: {scalar(entry['id'], True)}")
        lines.append(f"{pad}    title: {flow_multilang(entry['title'])}")
    return lines


def load_agent(agent_dir: Path) -> dict:
    path = agent_dir / "agent.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        fail(f"{path} 解析不了：{error}")
    if not isinstance(data, dict):
        fail(f"{path}: 顶层要是映射")
    unknown = sorted(set(data) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        fail(f"{path}: 不认识的字段 {', '.join(unknown)}")
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        fail(f"{path}: 缺字段 {', '.join(missing)}")
    if not ID_RE.match(str(data["id"])):
        fail(f"{path}: id 要是至少两段的反向域名（小写字母、数字和单个连字符），如 ai.echo")
    if not VERSION_RE.match(str(data["version"])):
        fail(f"{path}: version 要是语义化版本，如 0.1.0")
    if data["acp_mode"] not in ACP_MODES:
        fail(f"{path}: acp_mode {data['acp_mode']!r} 不在桥的白名单 {list(ACP_MODES)} 里"
             f"（config.rs 的 ALLOWED_MODES），装机会在桥启动时退")
    if "acp_topic_mode" in data and data["acp_topic_mode"] not in ACP_MODES:
        fail(f"{path}: acp_topic_mode {data['acp_topic_mode']!r} 不在桥的白名单 {list(ACP_MODES)} 里，"
             f"装机会在桥启动时退")
    for entry in data.get("login") or []:
        if (not isinstance(entry, dict) or set(entry) != {"id", "title"}
                or not LOGIN_ID_RE.match(str(entry.get("id", "")))):
            fail(f"{path}: login 每项只要 id（小写字母、数字和单个连字符）和 title")
    if data.get("webui") not in (None, True):
        fail(f"{path}: webui 只支持 true（登录网页端口由模板定死 8080）")
    return data


def inline(key: str, agent: dict, name: str) -> str:
    if key == "NAME":
        return name
    if key == "VERSION":
        return str(agent["version"])
    if key == "ID":
        return str(agent["id"])
    if key == "ACP_MODE":
        return scalar(agent["acp_mode"])
    if key == "MEMORY":
        return scalar(agent["memory"])
    if key == "DISPLAY_NAME":
        return flow_multilang(agent["title"])
    fail(f"模板里有不认识的占位符 @@{key}@@")


def fragment(key: str, agent: dict, name: str, web_text: str) -> list[str]:
    """整行占位符的展开；空片段时这一行整个消失。"""
    if key == "AGENT_ENV":
        return env_lines(agent.get("env") or {})
    if key == "ACP_TOPIC_MODE":
        mode = agent.get("acp_topic_mode")
        return [f"      WONTON_ACP_TOPIC_MODE: {scalar(mode)}"] if mode else []
    if key == "WEB_SERVICE":
        if not agent.get("webui"):
            return []
        return [HOLE.sub(lambda m: inline(m.group(1), agent, name), line)
                for line in web_text.split("\n")]
    if key == "TITLE":
        return [f"  title: {flow_multilang(agent['title'])}"]
    if key == "DESCRIPTION":
        return block_multilang("description", agent["description"])
    if key == "NOTICES":
        return [f"  notices: {scalar(list(agent['notices']))}"]
    if key == "HOMEPAGE":
        return [f"  homepage: {scalar(agent['homepage'])}"]
    if key == "LICENSE":
        return [f"  license: {scalar(agent['license'])}"]
    if key == "TAGS":
        return [f"  tags: {flow_multilang(agent['tags'])}"] if agent.get("tags") else []
    if key == "ABOUT":
        return block_multilang("about", agent["about"])
    if key == "RELEASE_NOTES":
        return block_multilang("release_notes", agent["release_notes"])
    if key == "WEBUI":
        return ["  webui:", "    service: web", "    port: 8080", "    sso: none"] if agent.get("webui") else []
    if key == "LOGIN":
        return login_block(agent["login"]) if agent.get("login") else []
    if key == "EXTRA_PERMISSIONS":
        return [f"    - {perm}" for perm in agent.get("permissions") or []]
    fail(f"模板里有不认识的占位符 @@{key}@@")


def render(agent: dict, name: str, compose_text: str, web_text: str) -> str:
    lines = []
    for line in compose_text.split("\n"):
        whole = WHOLE_HOLE.match(line)
        if whole:
            lines += fragment(whole.group(1), agent, name, web_text)
        else:
            lines.append(HOLE.sub(lambda m: inline(m.group(1), agent, name), line))
    return "\n".join(lines)


def self_image_digest(agent_dir: Path, agent: dict) -> str:
    """compose 里发布写回的自身镜像摘要（publish.sh 的 pin_image 写的）：和清单版本一致才带进生成结果。
    版本不一致的是发旧版本时的旧摘要，丢掉；同版本出现两种摘要说明 compose 被手改过，报错不猜。"""
    path = agent_dir / COMPOSE_NAME
    if not path.exists():
        return ""
    digest = ""
    # 匹配规则和 publish.sh 的 pin_image 一致：逐行扫 image 行。
    line = re.compile(rf"^\s*image:\s*(?:&\S+\s+)?\S+/{re.escape(agent_dir.name)}"
                      rf":{re.escape(str(agent['version']))}@(sha256:[0-9a-f]{{64}})(\s*(?:#.*)?)$")
    for text_line in path.read_text(encoding="utf-8").split("\n"):
        match = line.match(text_line)
        if not match:
            continue
        if digest and match.group(1) != digest:
            fail(f"{path}: 版本 {agent['version']} 的自身镜像摘要有两种（{digest} 和 {match.group(1)}）,"
                 f"删到只剩发布写回的那个")
        digest = match.group(1)
    return digest


def render_compose(agent_dir: Path, agent: dict) -> str:
    compose_text = (TEMPLATE_DIR / "compose.yml").read_text(encoding="utf-8")
    web_path = TEMPLATE_DIR / "web-service.yml"
    web_text = web_path.read_text(encoding="utf-8") if web_path.exists() else ""
    text = render(agent, agent_dir.name, compose_text, web_text)
    digest = self_image_digest(agent_dir, agent)
    if not digest:
        return text
    # 匹配规则和 publish.sh 的 pin_image 一致，行尾注释和 YAML 锚点也照它保留。
    pattern = re.compile(rf"^(\s*image:\s*(?:&\S+\s+)?)(\S+/{re.escape(agent_dir.name)}"
                         rf":{re.escape(str(agent['version']))})(\s*(?:#.*)?)$")
    pinned = []
    for line in text.split("\n"):
        match = pattern.match(line)
        pinned.append(f"{match.group(1)}{match.group(2)}@{digest}{match.group(3)}" if match else line)
    return "\n".join(pinned)


def agent_dirs(paths: list[str]) -> list[Path]:
    if paths:
        dirs = [Path(p) for p in paths]
        for directory in dirs:
            if not (directory / "agent.yaml").exists():
                fail(f"{directory}: 没有 agent.yaml")
        return dirs
    agents = ROOT / "agents"
    if not agents.is_dir():
        return []
    return sorted(path for path in agents.iterdir() if (path / "agent.yaml").exists())


def main() -> None:
    args = sys.argv[1:]
    check = "--check" in args
    if "--check" in args:
        args.remove("--check")
    if [arg for arg in args if arg.startswith("-")]:
        fail(f"不认识的参数：{' '.join(arg for arg in args if arg.startswith('-'))}")
    stale = []
    for directory in agent_dirs(args):
        output = render_compose(directory, load_agent(directory))
        path = directory / COMPOSE_NAME
        if path.exists() and path.read_text(encoding="utf-8") == output:
            continue
        if check:
            stale.append(f"{path}: 不是最新的，跑 python3 gen/gen.py {directory}")
            continue
        path.write_text(output, encoding="utf-8")
        print(f"写 {path}")
    if stale:
        print("\n".join(stale), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
