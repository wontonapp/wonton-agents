# OpenCode 插件

[OpenCode](https://opencode.ai)（MIT）的 Wonton 接入：ACP 命令 `opencode acp`，官方二进制首次启动时
从上游发布 CDN 按摘要下载到数据卷，主模型和辅助模型只通过 magpie 模型网关，不提供 key 登录或登录网页。

## 实测记录（2.2.7）

- **最严格模式**：`plan`（agent.yaml 的 `acp_mode`，桥在主会话 `session/new` 后经 `session/set_mode`
  切过去；会话的 configOptions 里 modes = build / plan 两个）。注意 opencode 内置 agent 的缺省
  权限是放开一切（`Agent.Info` 的缺省 ruleset 是 allow-all，只对读 `.env` 先问），plan 模式的
  「只读」是 agent 自己的规则；本插件的网关钩子把 `edit`、`shell` 显式写成 `ask`，所以 plan 和
  build 两种模式下改文件、跑命令都会出确认卡片（实测：plan 下 write 触发
  `session/request_permission`，`allow_once` 后文件落盘）。话题会话跟随主会话模式：清单原本配的
  `acp_topic_mode: build` 不在桥的模式白名单里（桥会因它启动失败），0.1.2 起去掉该字段，主、
  话题会话同为 plan，改前先问的语义一致。
- **只放行 Wonton MCP 的配置键**：`opencode.json` 的 `permissions` 里
  `{"action": "wonton_*", "resource": "*", "effect": "allow"}`。桥按会话把核心的 MCP 入口作为
  HTTP 服务器传进 `session/new` 的 `mcpServers`（opencode 只收 http/stdin 两类，实测收到
  `type: "http"` 就注册成 remote 服务器）；MCP 工具的权限动作是「服务器名_工具名」，`wonton_*`
  一条盖住（`*` 也吃下划线）。工具名本身来自核心总线的 `wonton__<工具>`（实测 agent 容器里对
  `mcp.wonton.internal` 的 Streamable HTTP `tools/list` 能列出 `wonton__list_plugins` 等）。
- **内存峰值**：agent 容器常驻约 165 MiB，跑模型对话时约 166 MiB（1.5B 本地模型、短会话；
  docker stats 实测），清单按 512M 留了余量。更大的模型和长会话会更高，超限时核心显示插件
  被杀/未就绪，不静默重试。
- **网关写法**：`providers.magpie`（V2 的复数键；实测 V1 的单数 `provider` 键走迁移、丢
  `package`，报 "Unsupported package"）。`package` 用内置的
  `@opencode/ai/providers/openai-compatible`，`settings.baseURL` 使用 `WONTON_MODEL_BASE_URL`。
  `model` 和 `agents` 中的 build、plan、general、explore、title、summary、compaction 都指定
  `magpie/<WONTON_MODEL_DEFAULT>`，辅助任务不会自动选官方小模型。
  密钥不落盘：`env: ["WONTON_MODEL_API_KEY"]` 引用环境变量，值由底座传入子进程。
- **提供者限制**：按上游 [Policies](https://opencode.ai/docs/policies/) 和
  [配置 schema](https://opencode.ai/config.json)，`policies` 先 `provider.use` 拒绝 `*`，
  再放行 `magpie`（后匹配覆盖前匹配），已保存账号和内置免费模型也受此限制；
  `integration.connect` 拒绝 `*`，不把上游连接账号或 key 的界面作为替代模型入口。
  MCP 工具规则、文件和命令确认卡片保持不变。
- **未就绪**：缺少网关配置时底座不启动模型会话；网关不可用或凭据失败时明确报错，不切换来源。
  `clear` 报未就绪，保留配置，不恢复旧提供者、key、账号或免费模型。

## 已知限制

- 首次启动要从上游 CDN 下载约 112 MiB 的官方二进制：核心的安装期限
  （`WONTON_INSTALL_TIMEOUT_SECS`，默认 300s）和模板健康检查的 `start_period`（300s）在慢网络
  上都可能挡住首装，核心会回滚安装（数据卷保留，重装时秒级就绪）。机器慢的话先把核心的
  `WONTON_INSTALL_TIMEOUT_SECS` 调大。
- 上游 `/model`、`/connect` 和 `auth` 命令仍存在；当前配置限制可用提供者和连接入口，不修改上游源码。
  项目模型覆盖不能使用被全局策略拒绝的其他提供者，但项目仍可重定义 magpie 的端点，用户也可手动
  修改全局配置或另起上游 CLI。这是配置级来源约束，不是网络级封锁；已保存的旧会话若引用其他提供者
  应报不可用，而不是自动恢复原来的直连。
