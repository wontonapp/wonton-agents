# OpenCode 插件

[OpenCode](https://opencode.ai)（MIT）的 Wonton 接入：ACP 命令 `opencode acp`，官方二进制首次启动时
从上游发布 CDN 按摘要下载到数据卷，模型默认走云吞的模型网关，官方账号经终端登录。

## 实测记录（2.2.7）

- **最严格模式**：`plan`（agent.yaml 的 `acp_mode`，桥在主会话 `session/new` 后经 `session/set_mode`
  切过去；会话的 configOptions 里 modes = build / plan 两个）。注意 opencode 内置 agent 的缺省
  权限是放开一切（`Agent.Info` 的缺省 ruleset 是 allow-all，只对读 `.env` 先问），plan 模式的
  「只读」是 agent 自己的规则；本插件的网关钩子把 `edit`、`shell` 显式写成 `ask`，所以 plan 和
  build 两种模式下改文件、跑命令都会出确认卡片（实测：plan 下 write 触发
  `session/request_permission`，`allow_once` 后文件落盘）。话题会话用 `acp_topic_mode: build`，
  改前先问的语义一致。
- **只放行 Wonton MCP 的配置键**：`opencode.json` 的 `permissions` 里
  `{"action": "wonton_*", "resource": "*", "effect": "allow"}`。桥按会话把核心的 MCP 入口作为
  HTTP 服务器传进 `session/new` 的 `mcpServers`（opencode 只收 http/stdin 两类，实测收到
  `type: "http"` 就注册成 remote 服务器）；MCP 工具的权限动作是「服务器名_工具名」，`wonton_*`
  一条盖住（`*` 也吃下划线）。工具名本身来自核心总线的 `wonton__<工具>`（实测 agent 容器里对
  `mcp.wonton.internal` 的 Streamable HTTP `tools/list` 能列出 `wonton__list_plugins` 等）。
- **内存峰值**：agent 容器常驻约 165 MiB，跑模型对话时约 166 MiB（1.5B 本地模型、短会话；
  docker stats 实测），清单按 512M 留了余量。更大的模型和长会话会更高，超限时核心显示插件
  被杀/未就绪，不静默重试。
- **网关写法**：`providers.wonton`（V2 的复数键；实测 V1 的单数 `provider` 键走迁移、丢
  `package`，报 "Unsupported package"）。`package` 用内置的
  `@opencode/ai/providers/openai-compatible`，`settings.baseURL` 直接用 `WONTON_MODEL_BASE_URL`
  （带 `/v1`），模型 id 用 `WONTON_MODEL_DEFAULT` 原样（带斜杠也能用，模型引用
  `wonton/<DEFAULT>`）。密钥不落盘：`env: ["WONTON_MODEL_API_KEY"]` 引用环境变量，值由底座的
  子进程环境带进去。
- **登录**：opencode 2.2.7 的密钥输入要真终端（管道上直接报
  "API key input requires an interactive terminal"），所以 `[[login]]` 的包装脚本起 pty 跑官方
  `opencode auth login opencode --method key`，把底座登录通道的一行 key 写进 pty（回显关掉）。
  状态查询用 `opencode auth list --format json`（凭据在上游自己的 SQLite 里）。

## 已知限制

- 首次启动要从上游 CDN 下载约 112 MiB 的官方二进制：核心的安装期限
  （`WONTON_INSTALL_TIMEOUT_SECS`，默认 300s）和模板健康检查的 `start_period`（300s）在慢网络
  上都可能挡住首装，核心会回滚安装（数据卷保留，重装时秒级就绪）。机器慢的话先把核心的
  `WONTON_INSTALL_TIMEOUT_SECS` 调大。
- 没接模型网关、也没登录官方账号时，opencode 会用它自己托管的免费模型回答（上游行为）；插件
  不改这个行为，但在网关就绪后核心重建容器、钩子写好网关配置，即自动切回云吞网关。
