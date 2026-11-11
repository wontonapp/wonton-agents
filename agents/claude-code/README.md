# Claude Code

Anthropic 的 Claude Code 编程 Agent，经官方 ACP 适配器（`@agentclientprotocol/claude-agent-acp`）
接 Wonton 的桥，以 Bot 身份住在聊天里：改文件、跑命令之前出确认卡片，同意才动手；Wonton 其他
插件的工具经 MCP 总线从聊天里调。闭源 CLI 不打进镜像，容器首次启动按 `image/agent.toml` 的
`[[install]]` 从官方 npm registry 按摘要下载到数据卷。

本目录是 [仓库 README](../../README.md#新增一家)里「新增一家」清单的一个实例：

- `agent.yaml`：清单来源（id、版本、商店文字、登录方式、`acp_mode`、内存、环境变量），`docker-compose.yml` 由 `gen/` 生成
- `image/agent.toml` + `image/Dockerfile`：子镜像的全部差异（装哪个 CLI、ACP 怎么启动、网关钩子、登录）
- `image/gateway`：把 `WONTON_MODEL_*` 写进 Claude Code 的用户设置 `env`（`apply`），`clear` 按备份还原；密钥落盘的文件 0600
- `image/oauth-login`、`auth-status`、`api-key-login`、`api-key`、`api-key-status`：三种终端登录
- `image/web-proxy`：登录网页的转发（模板里 `web` 服务的入口）
- `smoke-probes.sh`：冒烟探针

模型有两个来源，每次容器启动时选定：接上模型网关（要提供 Anthropic Messages 接口）时默认走网关，
不用账号；没接时用登录态（三种方式：Claude 订阅、Anthropic Console、API key）。Claude Code 只讲
Anthropic Messages，OpenAI 兼容地址喂不进去，网关没有 Anthropic 接口时按没接网关处理。

## 实测记录

- **最严格的模式：`default`**（`agent.yaml` 的 `acp_mode`，经 `WONTON_ACP_MODE` 传给桥）。每次改文件、
  跑命令都出确认卡片，主人同意才执行；适配器还支持 `acceptEdits`、`plan`、`auto`、`bypassPermissions`
  （非 root 才有），都比 `default` 宽松。
- **只放行 Wonton MCP 的配置键：没有单独的键，也不需要。** MCP 服务只从 ACP 会话进来（桥把
  `mcpServers` 交给适配器），插件自己不配置任何 MCP 源，Claude Code 也没有 MCP 白名单键；
  镜像里的 `image/managed-settings.json` 只 deny `ToolSearch`（配置环境变量 `ENABLE_TOOL_SEARCH=false`），
  让 Wonton 工具直接进工具表，不经过延迟加载。
- **内存峰值：238 MiB**（容器上限 4G）。实测环境：开发栈，桥 0.2.1，模型是脚本化的假上游（见下），
  一轮「列文件 + 建文件 + 子代理」对话、三张权限卡片批准、再一轮全部拒绝的过程中每 2 秒采样，
  85 个样本的峰值；空闲态 84 MiB。真实模型（流式更长、上下文更大）峰值会略高，链路各环节（CLI、适配器、
  转发）的占用不变。
- **上表数据用的模型是假上游**：任务约定不填真实 key，实测用一台脚本化的假模型服务（说 Anthropic Messages
  SSE，按工具结果数推进脚本：ls → touch → Write → TodoWrite → 子代理 → 收尾），经开发栈的 magpie 网关
  挂成 provider，用量记账在 magpie 里（`magpie usage` 见 provider=mockmodel）。真实模型下「工具调用
  质量」不验，也没验：这不是本插件能决定的（CLI 与上游交互未改动）。
