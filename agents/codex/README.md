# Codex

OpenAI Codex 作为 Bot 住进聊天。这一目录是它自己的差异：`agent.yaml`（清单）、
`image/`（`agent.toml`、网关钩子、登录、提示词、skill）、`NOTICE`、图标和冒烟探针。
桥、底座和 compose 由仓库共用，不在这里。

## 实测记录（0.1.0，Codex CLI 0.166.0 + codex-acp 2.6.0）

- **最严格的模式**：`read-only`。Codex 自带的沙箱在普通 Docker 容器里建不了命名空间，
  更宽的模式不可用；`read-only` 下改文件、跑命令都会经确认卡片问主人，钩子因此把
  `use_legacy_landlock` 写进 `[features]`（bubblewrap 的 userns 在容器里起不了）。
- **只放行 Wonton MCP 的配置键**：没有。Wonton 的 MCP 入口由桥在会话里以 `mcpServers`
  （HTTP）传给 codex-acp，适配器写进会话配置；它会把 config.toml 里已定义的同名服务器
  跳过，所以网关钩子不写任何 `mcp_servers` 段，Wonton 工具的确认卡片由核心出。
- **内存峰值**：见下方实测（工作区一轮对话 + 一次改文件确认，`docker stats` 采样）。

## 模型和登录

模型网关接好时（三个 `WONTON_MODEL_*` 都有值），网关钩子把网关写进
`$CODEX_HOME/config.toml`：`model_provider`、`model`、`model_catalog_json` 和
`[model_providers.wonton]`；API key 只以 `env_key = "OPENAI_API_KEY"` 引用变量名，
值由底座经 `[gateway.env]` 注进 ACP 子进程。已有 ChatGPT 登录态时官方直连优先，
钩子清掉网关配置。

没接网关时用官方账号：聊天里 `/wonton login`（设备码登录 ChatGPT，或贴 API key），
或打开登录网页（插件页）做同样的事。登录态在数据卷 `$CODEX_HOME/auth.json` 里，
容器重建后还在。

## 上游版本

版本和摘要写在 `image/agent.toml` 的 `[[install]]`（npm dist.integrity），注册表机器人在
上游出新版时提 PR。Codex CLI 由适配器的 npm 依赖带进来，包里没有 shrinkwrap，跟随
semver。
