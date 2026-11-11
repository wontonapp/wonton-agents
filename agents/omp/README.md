# omp

omp（[oh-my-pi](https://github.com/can1357/oh-my-pi)，MIT）以 Bot 的身份住进聊天，经桥说 ACP，模型走网关或它自己的
官方登录。目录结构和「新增一家」要写的东西见仓库根的 [README](../../README.md)。

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

底座把 `WONTON_MODEL_BASE_URL`、`WONTON_MODEL_API_KEY`、`WONTON_MODEL_DEFAULT` 交给 [image/gateway](image/gateway)：
`apply` 写 `~/.omp/agent/models.yml`（provider `wonton`，`api: openai-completions`，`apiKey` 只写变量名）和
`config.yml`（四个 `modelRoles` 都指向 `wonton/<模型>`），`clear` 把这两处移出去、其余内容保留。omp 对 `apiKey`
先当环境变量名读、取不到才当字面量，所以密钥不用落盘。

## 登录

`[[login]]` 用 `omp login`：官方登录的行式形态（选 provider、打印链接、收授权码和 key），全屏 TUI 那套在聊天里跑
不起来；在聊天里发 `/wonton login` 由桥转给登录 socket。凭据写进 HOME 下的 agent.db，容器重建后还在。上游没有
状态查询命令，`/wonton login` 列表的状态显示「不确定」。登录网页（清单 `webui`）要等底座把 `web-proxy` 补上再加，
见 PR 里的「底座的问题」。
