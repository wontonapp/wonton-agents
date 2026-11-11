# Kimi Code

Moonshot AI 的 [Kimi Code CLI](https://github.com/MoonshotAI/kimi-code)（npm 包
`@moonshot-ai/kimi-code`，MIT）接入 Wonton。桥服务、底座和开发脚本在仓库根的
[README](../../README.md)，本目录只写这一家的差异。

## 这一家写了什么

- `image/agent.toml`：首启从 npm 官方源按摘要下载 CLI；ACP 命令 `kimi acp`（包的 bin 字段
  指到包根的 `dist/main.mjs`，不是 `bin/` 下的文件）；登录网页端口 8080。
- `image/kimi_config.py`：`~/.kimi-code/config.toml` 的托管，网关钩子和登录脚本共用。
  文件分三段：顶部的 `default_model`、`[[permission.rules]]`（固定内容）、两段带
  `# BEGIN/END WONTON` 标记的块（网关、开放平台），其余内容逐字保留。
- `image/gateway`：底座网关钩子。`apply` 写 `providers.wonton`（`type = "openai"`、
  `base_url`、`api_key_env = "WONTON_MODEL_API_KEY"`）和模型别名 `wonton/default`，并把
  `default_model` 指过去；`clear` 移出去，`default_model` 指回平台 key 的默认模型（有）或删掉。
  密钥不落盘，key 只在环境变量里；不改 CLI 的 User-Agent。
- `image/login-platform-key`：Kimi 开放平台 API key 登录（platform.kimi.com）。读一行 key，
  先对平台 `/models` 验证，通过后照上游登录流程的写法把 `providers.moonshot-cn`
  （`type = "kimi"`）和模型别名写进配置，文件 0600；失败按原因报错，不写半套配置。
- `image/login-status`：`[[login]] status`，设备码登录看上游凭据文件
  `~/.kimi-code/credentials/kimi-code.json`，平台 key 看配置里的标记块。
- 上游模型别名带 `max_context_size = 262144`（kimi 对无目录来源模型的默认窗口）：
  不写这行，CLI 的模型解析判 unresolvable，会话建立报 Authentication required。

## 实测记录（kimi-code 2.5.3）

- **最严格的模式是 `plan`**：会话能力以 `session/new` 应答的 `configOptions`（`category:
  "mode"`）通告，取值 `default`/`plan`/`auto`/`yolo`，桥用 `session/set_config_option` 切。
  `plan` 下不执行任何工具：让它写 `/workspace/hello.txt`，会话正常应答，文件没有创建。
  `default` 模式下动文件、跑命令出 ACP 权限卡（`approve_once`/`approve_always`/`reject`），
  由桥转成核心确认卡。
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
