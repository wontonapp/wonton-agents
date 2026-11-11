# Codex

OpenAI Codex 作为 Bot 住进聊天。这一目录是它自己的差异：`agent.yaml`（清单）、
`image/`（`agent.toml`、网关钩子、登录、提示词、skill）、`NOTICE`、图标和冒烟探针。
桥、底座和 compose 由仓库共用，不在这里。

## 实测记录（0.1.0，Codex CLI 0.166.0 + codex-acp 2.6.0）

- **最严格的模式**：`read-only`。改文件必须出确认卡片。实测里 MCP 工具的确认卡片
  正常（请求、允许、拒绝都对得上）；但 Codex 0.166 在普通 Docker 容器里跑不了受限
  沙箱下的命令（见下方已知限制），改文件的卡片在这台环境出不来。
- **只放行 Wonton MCP 的配置键**：没有。Wonton 的 MCP 入口由桥在会话里以 `mcpServers`
  （HTTP）传给 codex-acp，适配器写进会话配置；它会把 config.toml 里已定义的同名服务器
  跳过，所以网关钩子不写任何 `mcp_servers` 段，Wonton 工具的确认卡片由核心出。
- **经网关回答一句话**：适配器到网关的整条线验证过（网关鉴权、模型路由、
  `model_provider`/`model_catalog_json`/`env_key` 都按预期工作）。开发机上没有配上游
  模型，回答是用探针把网关指向本机 mock 模型跑通的；真实上游一句话未验证。
- **内存峰值**：agent 容器 cgroup `memory.peak` 102 MiB（一轮对话 + 一次改文件确认，
  适配器与 app-server 都在这容器里）；桥 11 MiB。

## 已知限制：受限沙箱在这类容器里跑不了

Codex 0.166 起要求受限模式（read-only、workspace-write）的命令在 bubblewrap 的
mount/user namespace 里跑，`use_legacy_landlock` 也一样（带受限文件系统策略时直接
拒绝启动沙箱）。Docker 默认 seccomp 禁止容器里建 user namespace，宿主内核又开着
`apparmor_restrict_unprivileged_userns`，bubblewrap 起不来。结果：这两种模式里命令
一律失败退出，写不进去（fail-closed），但确认卡片流程也不会触发。要恢复，得让容器
允许建 user namespace（compose 加 seccomp 白名单或宿主关掉上述 sysctl），这要改共用
模板，见 PR 说明。

## 模型和登录

模型网关接好时（三个 `WONTON_MODEL_*` 都有值），网关钩子把网关写进
`$CODEX_HOME/config.toml`：`model_provider`、`model`、`model_catalog_json` 和
`[model_providers.wonton]`；API key 只以 `env_key = "OPENAI_API_KEY"` 引用变量名，
值由底座经 `[gateway.env]` 注进 ACP 子进程。任一变量为空时钩子清掉网关配置，
改用官方登录态。

官方账号登录：聊天里 `/wonton login`（设备码登录 ChatGPT，或贴 API key），或打开
登录网页（插件页）做同样的事。设备码链接由桥发进聊天，容器里没有浏览器。登录态在
数据卷 `$CODEX_HOME/auth.json` 里，容器重建后还在。

实测：initialize 应答的 `authMethods` 已改写成清单里的两种登录；登录命令经网页接口
起停和输出流式转发都正常（设备码请求在本机被 auth.openai.com 拒了 403，流程本身
通了，真实出码未验证）。

## 上游版本

适配器和 Codex CLI 都是 Apache-2.0 的开源 npm 包，打进镜像（`image/Dockerfile` 按
npm dist.integrity 固定）。适配器依赖 `@openai/codex ^0.166.0`，包里没有 shrinkwrap，
CLI 版本跟随 semver；注册表机器人在上游出新版时提 PR。
