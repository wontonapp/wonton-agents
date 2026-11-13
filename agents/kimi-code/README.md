# Kimi Code

Moonshot AI 的 [Kimi Code CLI](https://github.com/MoonshotAI/kimi-code)（npm 包
`@moonshot-ai/kimi-code`，MIT）接入 Wonton。桥服务、底座和开发脚本在仓库根的
[README](../../README.md)，本目录只写这一家的差异。

## 这一家写了什么

- `image/agent.toml`：首启从 npm 官方源按摘要下载 CLI；ACP 命令 `kimi acp`（包的 bin 字段
  指到包根的 `dist/main.mjs`，不是 `bin/` 下的文件）；登录网页端口 8080。
- `image/kimi_config.py`：托管 `~/.kimi-code/config.toml`。网关模式只保留 magpie 模型目录，
  官方模式只保留有 OAuth 的原生订阅目录；工具、权限和订阅凭据保留，配置文件 0600。
- `image/gateway`：默认和 `secondary_model.default_model`（全部 Agent/AgentSwarm 子代理）指向
  `magpie/default`，密钥只以 `api_key_env = "WONTON_MODEL_API_KEY"` 引用，不写值。
  官方清除必须收到底座的 `WONTON_AGENT_MODEL_SOURCE=official`，只选择实际 OAuth 订阅的原生模型，
  不恢复平台 key 或备份；缺少订阅模型目录就报错并要求重新完成设备码登录。
- `image/acp-launch`：移除继承的 `KIMI_MODEL_*`、`KIMI_API_KEY`、`KIMI_BASE_URL` 模型覆盖再启动上游。
- `image/login-status`：显示设备码订阅凭据状态；凭据存在不自动选模型来源。

## 模型来源与上游边界

默认走 magpie；网关变量缺失时明确报“未就绪”，不会调用其他服务，登录控制仍可用。
在登录网页或 `/wonton login` 明确完成 Kimi 账号设备码登录后才选官方订阅；网关是否可用不会改来源。
选择“magpie 模型网关”切回网关。不提供开放平台 API key 登录。

检查了固定 npm 版本 2.5.3 的入口和模型配置：`kimi acp --login` 专门运行设备码登录，
不使用带其他 provider 选项的通用登录入口。`secondary_model` 单独设置 `default_model` 会固定全部子代理，
原来的可选模型池不会保留。明确运行 `acp --login` 时，上游会重新生成原生订阅模型目录，
官方清除再显式选择其中的模型，不能沿用登录前的 magpie 默认值。运行中的上游 `/login`、
`/model`、ACP 模型选择及配置修改仍属于上游界面；这不是网络级隔离，不修改上游源码。
参见 [上游源码](https://github.com/MoonshotAI/kimi-code)。

## 实测记录（kimi-code 2.5.3）

- **最严格的模式是 `plan`**：会话能力以 `session/new` 应答的 `configOptions`（`category:
  "mode"`）通告，取值 `default`/`plan`/`auto`/`yolo`，桥用 `session/set_config_option` 切。
  `plan` 下不执行任何工具：让它写 `/workspace/hello.txt`，会话正常应答，文件没有创建。
  `default` 模式下动文件、跑命令出 ACP 权限卡（`approve_once`/`approve_always`/`reject`），
  由桥转成核心确认卡。清单 `acp_mode` 从 0.1.3 起用 `default`（0.1.2 配过 `plan`，上游
  plan 语义=不执行任何工具，与插件说明承诺的确认卡不符）。
- **只放行 Wonton MCP 的配置键**：`[[permission.rules]]`，`decision = "allow"`，
  `pattern = "mcp__wonton__*"`（桥传进来的服务器名是 `wonton`，工具名前缀 `mcp__wonton__`）。
  注意：2.5.3 的运行时不读配置里的规则（上游 `permissionRulesService` 不接 user 配置，
  实测照旧出权限卡），上游 main 已经改成实时读；这条规则随注册表机器人升到修复版后生效。
  生效前 Agent 调 Wonton 工具会有两张卡（核心一张、Agent 一张）。
- **MCP**：`agentCapabilities.mcpCapabilities.http = true`，桥把 Wonton MCP 以
  `{type: "http", name: "wonton", url, headers: []}` 传进 `session/new`，实测 `tools/list`
  发现的工具以 `mcp__wonton__list_plugins` 出现在模型请求里。
- **网关链路**：`config.toml` 的 `providers.wonton` + 模型别名 + `default_model`，实测请求
  打到网关的 `/v1/chat/completions`，带对模型名和 `Authorization: Bearer`（来自环境变量，
  配置里只有变量名）；UA 是 CLI 自带的（OpenAI SDK），没有动。
- **内存峰值**：一个会话跑一轮问答，kimi（node）进程 RSS 峰值约 270 MB，入口约 30 MB；
  清单 `memory: 512M` 留了约一倍余量。
