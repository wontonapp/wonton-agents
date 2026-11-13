# Claude Code

Anthropic 的 Claude Code 编程 Agent，经官方 ACP 适配器（`@agentclientprotocol/claude-agent-acp`）
接 Wonton 的桥，以 Bot 身份住在聊天里：改文件、跑命令之前出确认卡片，同意才动手；Wonton 其他
插件的工具经 MCP 总线从聊天里调。闭源 CLI 不打进镜像，容器首次启动按 `image/agent.toml` 的
`[[install]]` 从官方 npm registry 按摘要下载到数据卷。

本目录是 [仓库 README](../../README.md#新增一家)里「新增一家」清单的一个实例：

- `agent.yaml`：清单来源（id、版本、商店文字、登录方式、`acp_mode`、内存、环境变量），`docker-compose.yml` 由 `gen/` 生成
- `image/agent.toml` + `image/Dockerfile`：子镜像的全部差异（装哪个 CLI、ACP 怎么启动、网关钩子、登录）
- `image/gateway`：网关模式写入模型路由和各模型别名；官方模式删除外部 API 路由，不恢复旧备份，保留订阅凭据；设置文件 0600
- `image/oauth-login`、`auth-status`：只提供 Claude 订阅 OAuth 登录，不提供 Console API 计费或 API key 登录
- `image/acp-launch`：启动 ACP 前移除继承的外部模型、云 provider、API key 环境覆盖；工具和权限设置不变
- `smoke-probes.sh`：冒烟探针

默认使用 magpie 模型网关，且必须提供 `WONTON_MODEL_ANTHROPIC_BASE_URL`。缺少配置时明确报“未就绪”，
不清除路由、不启动模型会话，也不因旧 token/key 自动切来源。登录控制仍可使用。
在登录网页或 `/wonton login` 明确完成 Claude 订阅登录，底座才持久化官方来源；即使网关可用也保持官方模式。
选择“magpie 模型网关”可切回。官方清除要求底座传入 `WONTON_AGENT_MODEL_SOURCE=official`，不恢复旧 API 设置。

## 上游切换入口与边界

网关启动时将主模型、Haiku/Sonnet/Opus/Fable 别名、小任务和子代理模型统一指向网关默认模型，
移除用户设置中的 API key helper、外部 provider 和旧模型覆盖，并设置 `availableModels`。
依据 [模型配置](https://code.claude.com/docs/en/model-config) 的模型白名单缩小上游模型选择；
这些用户设置不是网络级隔离，项目/托管设置及运行中的 ACP 模型切换仍由上游处理。
[认证文档](https://code.claude.com/docs/en/authentication) 说明 `forceLoginMethod` 在终端交互登录只预选而不强制：
上游 `/login` 仍可能提供 Console/provider 选项，插件不修改上游，也不把这些路径列为支持的接法。
订阅登录命令固定 `auth login --claudeai`；网关凭据不代表订阅登录。

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
