# Qwen Code

Qwen Code（[QwenLM/qwen-code](https://github.com/QwenLM/qwen-code)，Apache-2.0）以 Bot 的身份住进聊天，经桥说 ACP，
模型只通过 magpie 模型网关，不提供 API key 登录或登录网页。目录结构见仓库根的 [README](../../README.md)。

## 实测记录

2026-11-11，qwen-code 0.27.2，开发栈实测（对话、确认卡片、工具调用都经桥）：

| 项 | 结果 |
| --- | --- |
| 最严格的模式 | `default`（TODO：实测后填） |
| 只放行 Wonton MCP 的配置键 | `settings.json` 的 `mcp.allowed = ["wonton"]`（TODO：实测后确认） |
| 内存峰值 | 见下 |

## 网关

底座把 `WONTON_MODEL_BASE_URL`、`WONTON_MODEL_API_KEY`、`WONTON_MODEL_DEFAULT` 交给 [image/gateway](image/gateway)：
`apply` 写 `~/.qwen/settings.json`：`modelProviders` 只保留 magpie 的 OpenAI 兼容条目，
`envKey` 只写 `OPENAI_API_KEY`，key 经底座 `[gateway.env]` 注入对话进程，不落盘。
`model.name`、`model.baseUrl`、认证选择和端点均指到网关，`security.auth.enforcedType = "openai"`；
删除旧配置中内联的认证 key，不保留其他提供者或备份还原逻辑。
快速模型、视觉模型、压缩模型和 batch 默认都指网关；已启用的顾问、图像、语音模型选择也重新指到网关，
未启用的可选功能不因此开启。`modelFallbacks` 为空，不配置备用模型。
MCP 的 Wonton 放行、自动更新关闭、工具确认和沙箱行为保持不变。

缺少配置或网关未就绪时，底座不启动模型会话；网关返回错误时直接显示错误，不改连别处。
`clear` 明确报未就绪，保留网关配置，不恢复旧认证类型、模型、端点或 key。

## 上游配置与限制

依据 qwen-code 0.27.2 已发布包的设置 schema，`security.auth.enforcedType` 能约束认证协议，
`modelProviders` 定义模型列表，`fastModel`、`visionModel`、`compactionModel`、`advisorModel`、
`imageModel`、`voiceModel` 和 `batch` 是独立模型选择入口。上游 `tools.webSearch` 使用专门的
DashScope Responses API 后端，不支持此网关协议，因此设为禁用；其他工具和 MCP 不变。

上游 `/auth`、`/model`、项目设置以及自定义子 Agent 的模型覆盖仍然存在；`enforcedType` 只约束协议，
不是端点白名单。用户自行编辑配置、恢复旧会话的模型覆盖或另起上游 CLI 仍可能绕开这些默认设置。
本插件不修改上游源码，也不声称这是网络级封锁。Qwen 账号的交互式 OAuth 没有作为插件订阅登录入口提供。
