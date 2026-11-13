# dsh

DeepSeek 的 dsh（DeepSeek Harness）住在云吞里：官方 npm 包 `@deepseek-ai/dsh`（MIT，打进镜像）经它自带的
`--profile acp` 说 ACP，用核心分配的 Matrix 身份和主人聊天，工具经 Wonton MCP 总线来。模型只通过
magpie 模型网关，不提供 API key 登录或登录网页。缺少网关配置、网关未就绪或凭据失败时如实报错，
不会改连官方服务、读取用户 key 作为备用来源；`clear` 也只报未就绪，不删除网关配置或恢复路由。

dsh 的会话日志和遥测默认回传上游，插件把它关了（`DSH_TELEMETRY_MODE=DISABLED`，
`session-log-deepseek` 不启用），会话日志不出容器。

## 实测记录

| 项 | 值 |
| --- | --- |
| 最严格的模式 | `workspace-write`（dsh 沙箱预设；`read-only` 下工具几乎全被拒，不可用） |
| 只放行 Wonton MCP 的配置键 | 不需要配置键：dsh 自己的配置（cordis.yml）默认不带任何 MCP 服务器，Wonton MCP 只经桥在 `session/new` 的 `mcpServers` 传入（dsh 的 ACP 声明 `mcpCapabilities.http`，直接挂 HTTP 总线；实测工具列表含 `mcp__wonton__*`） |
| 内存峰值 | agent 容器 263 MiB（多轮对话中采样，含一次沙箱升级请求），bridge 10 MiB；清单 1G 余量充足 |

dsh 的 ACP 不声明会话模式（`session/set_mode` 和模式类 `configOptions` 都没有），桥按 ACP 规范跳过切换
（桥 ≥0.2.1；更早的桥会对 dsh 发 `session/set_mode` 并被拒，会话建不起来）。沙箱预设固定为 dsh 自己的
默认 `workspace-write`：工作区内自由读写，`/tmp` 等平台临时区放行；工作区外的文件操作被沙箱拒绝并在
结果里提示升级，模型带 `sandbox_permissions` + `justification` 重试同一命令时才弹确认卡片，拒绝则不执行。

## 模型来源与上游限制

网关钩子重写活动 ACP profile 的 `cordis.patch.yml`，同时设置 `acp` 和 `agent-default-model` 的
`provider: magpie`、网关默认模型；子 Agent 按上游规则继承父会话的模型配置。
`llm-pi-ai.providers` 只声明 magpie，key 只引用 `WONTON_MODEL_API_KEY`，不写进补丁。
按上游 Cordis 的 `disabled: true` 配置禁用原生 `llm-deepseek`、`llm-deepseek-account` 两个直连适配器；
也禁用 `settings`，避免它首次启动时把旧 `settings.yaml` 的模型选择重新导入活动补丁。

上游 0.2.2-rc.1 的 `dsh-web-search-deepseek` 不经过 `ctx.llm`，而是直接向单独配置的
DeepSeek Messages API 发模型搜索请求；`dsh-web-deepseek-api` 也使用独立的 DeepSeek API 凭据。
它们不支持此 OpenAI 兼容网关协议，所以禁用这两个提供者：内置模型搜索不可用，不静默改用直连。
HTTP 网页读取、文件和命令工具、MCP、沙箱配置保持不变。

配置依据是相同版本已发布包 `dsh-base/cordis.patch.yml`、`dsh-acp-app/cordis.patch.yml`，以及
`dsh-subagent`、`dsh-settings`、`dsh-web-search-deepseek` 的实现。上游 ACP 模型选择仍然存在，
但只会列出当前注册的网关路由；用户若自行改 Cordis 配置、启用其他适配器或另起上游 CLI，仍可绕开
本插件管理的配置。本插件不修改上游源码，也不声称这是网络级封锁。

## 构建镜像

```sh
docker build -t ghcr.io/wontonapp/wonton-agents/dsh:<版本> agents/dsh/image
```

底座按摘要固定在 `image/Dockerfile` 的 FROM；底座升级改那一行重新构建。

## 图标

`icon.svg` 是按插件规范手绘的线条图标（小写 d 字形），原创。DeepSeek 和 dsh 是 DeepSeek 的商标；本插件不是
DeepSeek 的官方出品。来源、上游程序和许可证的说明见 [NOTICE](NOTICE)。
