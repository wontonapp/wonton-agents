# Qwen Code

Qwen Code（[QwenLM/qwen-code](https://github.com/QwenLM/qwen-code)，Apache-2.0）以 Bot 的身份住进聊天，经桥说 ACP，
模型走网关或它自己的 API key。目录结构和「新增一家」要写的东西见仓库根的 [README](../../README.md)。

## 实测记录

2026-11-11，qwen-code 0.27.2，开发栈实测（对话、确认卡片、工具调用都经桥）：

| 项 | 结果 |
| --- | --- |
| 最严格的模式 | `default`（TODO：实测后填） |
| 只放行 Wonton MCP 的配置键 | `settings.json` 的 `mcp.allowed = ["wonton"]`（TODO：实测后确认） |
| 内存峰值 | 见下 |

## 网关

底座把 `WONTON_MODEL_BASE_URL`、`WONTON_MODEL_API_KEY`、`WONTON_MODEL_DEFAULT` 交给 [image/gateway](image/gateway)：
`apply` 写 `~/.qwen/settings.json`——`modelProviders.openai` 加一条指向网关的条目（`envKey` 只写变量名
`OPENAI_API_KEY`，key 经底座的 `[gateway.env]` 注入对话进程，不落盘）、`model.name` 指到这条、
`security.auth.selectedType` 设成 `openai`；`clear` 逐键还原。两种模式都保证 `mcp.allowed = ["wonton"]`
（只放行桥在 session/new 里交给它的 Wonton MCP 服务器）和 `general.enableAutoUpdate = false`。

qwen-code 对 OpenAI 兼容认证认三个环境变量，没接网关时 compose 里带官方缺省端点和模型
（阿里云百炼的 OpenAI 兼容接口），API key 登录后就能用。

## 登录

只有 API key 一种：`[[login]]` 读一行 key 写进 `~/.qwen/.env`（0600），并把认证类型设成 `openai`。
qwen-code 0.27.2 删掉了 `qwen auth` 子命令，Qwen 账号的 OAuth 只剩交互 TUI 里的 `/auth`，聊天和登录网页的
行式输入跑不起来，所以没做账号登录；订阅用户请接模型网关。状态命令看 `.env` 里存没存 key。
