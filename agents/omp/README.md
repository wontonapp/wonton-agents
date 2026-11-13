# omp

omp（[oh-my-pi](https://github.com/can1357/oh-my-pi)，MIT）以 Bot 的身份住进聊天，经桥说 ACP，默认走 magpie；
只有主人明确完成官方订阅登录才切换来源。目录结构见仓库根的 [README](../../README.md)。

## 实测记录

2026-11-11，omp 18.16.0，开发栈实测（对话、确认卡片、工具调用都经桥）：

| 项 | 结果 |
| --- | --- |
| 最严格的模式 | `plan`。ACP 里只有 `default` 和 `plan` 两档；`plan` 下改工作区先出计划、跑命令一律出确认卡片，清单的 `acp_mode` 就写它 |
| 只放行 Wonton MCP 的配置键 | 不需要配置。omp 的 MCP 工具是 write 档，ACP 会话里默认放行不出卡，Wonton 的确认卡片只出核心那张；要卡的（bash 等 exec 档）由 plan 模式出卡 |
| 内存峰值 | 见下 |

（表格里两项的结论是在会话里让它调 Wonton 工具、跑命令后核对聊天里的卡片和 `docker stats` 得出的。）

内存：清单声明 1G。空闲常驻约 <空闲值>MiB，一轮带工具调用的对话峰值约 <峰值>MiB（`docker stats --no-stream`）。

## 网关

底座把 `WONTON_MODEL_BASE_URL`、`WONTON_MODEL_API_KEY`、`WONTON_MODEL_DEFAULT` 交给 [image/gateway](image/gateway)。
没有显式选择官方订阅时，即使已有 token 或 key，也仍然走 magpie；网关配置不齐会报告未就绪，不能回退直连。

`apply` 接管 `~/.omp/agent/models.yml` 和 `config.yml`，不备份、不恢复自定义 provider 或旧 key：
内部使用上游已有的 `litellm` provider 槽位承载 magpie 的 OpenAI-compatible 网关，`apiKey` 只写环境变量名，密钥不落盘。
`default`、`smol`、`slow`、`plan` 及其余聊天角色全部指向 `litellm/<模型>`；`enabledModels` 只放行当前精确模型，
`disabledProviders` 禁用固定上游版本的全部内置 provider（含本地免密 provider），而不只是改变默认模型。
已保存会话中的其他内置 provider 也受上游禁用检查约束。未提供相应能力的图片、语音等专用模型不改走别处。

`clear` 只接受底座传入 `WONTON_AGENT_MODEL_SOURCE=official` 和受支持的 `WONTON_AGENT_LOGIN_ID`。
它删除受管理的自定义模型文件，重写模型设置，只启用该次显式订阅登录对应的 provider；不恢复旧路由，也不选择 key。
ChatGPT 设备登录对应存储 provider `openai-codex`，其他登录 ID 与 provider 相同。
官方模式的具体默认模型由上游从该 provider 可用模型中选出。订阅凭据仍留在 `agent.db`，不受钩子修改。

## 登录

聊天里发 `/wonton login`，选择下列明确标记 `model_source = "official"` 的方式；成功后由底座保存选择。
也可以选择 `magpie 模型网关` 切回网关。没有泛用的 `omp login` 或自填模型 key 的入口。

| 订阅 | 固定上游命令 | 聊天可转发的流程 |
| --- | --- | --- |
| ChatGPT | `omp login openai-codex-device` | 浏览器设备码，凭据存为 `openai-codex` |
| GitHub Copilot | `omp login github-copilot` | GitHub 域名提示和设备码 |
| Kimi Code | `omp login kimi-code` | 浏览器设备码 |
| GitLab Duo | `omp login gitlab-duo-agent` | 浏览器授权，粘贴完整回调地址或授权码 |
| Factory Droid | `omp login factory-droid` | 浏览器设备码 |
| Muse Code | `omp login muse-code` | 浏览器设备码；上游用订阅授权换取请求凭据，不要求用户填 key |
| Grok | `omp login xai-oauth` | SuperGrok / X Premium+ 设备码 |
| Cursor | `omp login cursor` | 浏览器授权，上游轮询完成 |
| Perplexity | `PI_AUTH_NO_BORROW=1 omp login perplexity` | 邮箱验证码；禁用借用本机桌面登录态 |

以上是固定 **18.16.0 源码核对**，不是本次登录实测：
[CLI 参数](https://github.com/can1357/oh-my-pi/blob/v18.16.0/packages/coding-agent/src/commands/login.ts)、
[行式登录](https://github.com/can1357/oh-my-pi/blob/v18.16.0/packages/coding-agent/src/cli/login-cli.ts)、
[授权转发](https://github.com/can1357/oh-my-pi/blob/v18.16.0/packages/coding-agent/src/cli/oauth-terminal.ts)、
[认证策略](https://github.com/can1357/oh-my-pi/tree/v18.16.0/packages/catalog/src/compat/rules/auth)。
该版本允许 `login [provider]` 位置参数，不需要新增登录实现；省略参数会列出包括 key 在内的所有登录方式，故不暴露。
Anthropic、Google、浏览器版 Codex 等 OAuth 使用容器本地回调，行式登录不为其提供粘贴兜底，因此不列为聊天登录方式；
ChatGPT 改用上游已有的设备码流程。Mistral 的上游登录返回普通 API key，不能表达本插件要求的纯订阅凭据选择，故不暴露。
登录状态没有独立探测命令，列表显示「不确定」。本次没有运行登录、读取宿主凭据或联系模型服务。
Z.AI / Alibaba 等要求粘贴或生成普通计费 key 的方式也不列入订阅入口；Perplexity 只保留邮箱验证码订阅登录。

## 上游切换入口的边界

[模型文档](https://github.com/can1357/oh-my-pi/blob/v18.16.0/docs/models.md)说明：`enabledProviders` 仅控制外部配置发现，
并非模型传输白名单，因此这里使用 `disabledProviders`，同时重写受管理的模型列表和角色。
上游 `/model`、模型预设、会话恢复和 ACP 模型设置仍然存在；禁用 provider 会在模型解析和取凭据时被排除。
`enabledModels` 仅限制聊天模型，非聊天模型不能仅靠它限制，因此也必须禁用其他内置 provider。

这些是启动时的受管理默认值，不是网络级强制策略：项目 `.omp/config.yml`、项目模型配置、扩展注册 provider、
运行中 `/login` / 设置修改以及更高优先级配置仍由上游支持。新注册的 provider 不在固定内置禁用表内；
项目覆盖或直接修改设置也可能改变可选来源，插件不修改上游源码来封锁这些能力。
官方模式下上游优先取已登录 OAuth，但上游自身仍保留 key 的凭据兜底层；在上游注销或自行改配置后不能把它视为纯订阅沙箱。
要完全禁止这些绕过需要上游增加不可覆盖的来源/凭据策略，或另行实施网络隔离；本插件不声称已做到。
ACP `plan` 模式、工具权限和 Wonton MCP 的确认行为保持不变。
