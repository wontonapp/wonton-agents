# wonton-agents

Wonton 的 ACP Agent 插件：一个仓库，一个底座，每家 Agent 一个子目录。桥服务、底座入口、开发脚本和 CI 在这里共用；
每家只写自己躲不开的那几样。

```
base/                 底座镜像（ghcr.io/wontonapp/wonton-agent-base）：ACP 转发、终端登录和登录网页、闭源 CLI 首次启动下载
template/             公共 compose 模板（桥服务、agent 服务骨架、x-wonton 公共部分）
gen/                  生成器：agents/<id>/agent.yaml + template → agents/<id>/docker-compose.yml
agents/<id>/          每家一个插件包
scripts/              开发脚本，按 WONTON_PLUGIN 指定的子目录运行
.github/workflows/    检查、发布、注册表版本机器人
```

`agents/<id>/` 是一个独立的插件包，插件 id、版本、许可证和商店条目都分开。仓库只是一起维护，核心仍把每个子目录当
一个插件。

## 底座

底座把「装哪个 CLI、ACP 怎么启动、网关钩子、登录」交给 `agent.toml`，统一做 stdio↔socket 转发和登录 socket。子镜像
只写这几项配置。底座自己的说明、`agent.toml` 字段、样例和测试在 [base/](base/)。

```sh
python3 base/scripts/check-size.py
python3 -m unittest discover -s base/tests -v
docker build -t ghcr.io/wontonapp/wonton-agent-base:dev base
```

## 新增一家

一个子目录里要写这些文件；`agent.yaml` 是清单的来源，`docker-compose.yml` 由 `gen/` 生成，不要手改。

| 文件 | 内容 |
| --- | --- |
| `agent.yaml` | 插件 id、版本、标题和简介、许可证、notices、图标、登录方式、`acp_mode`、`acp_topic_mode`、内存、额外的环境变量、`webui`（可选）、额外权限 |
| `image/Dockerfile` | 从固定在摘要上的底座开始，`COPY` 本目录的 `agent.toml`、网关钩子、登录脚本、`prompt.md`、`skills/` |
| `image/agent.toml` | 这家的安装来源和摘要、ACP 启动命令、网关钩子、`[[login]]` |
| `image/<网关钩子>` | 把 `WONTON_MODEL_*` 写进这家的配置（`apply`），再改回来（`clear`）；密钥只留变量名 |
| `image/<登录脚本>` | 终端登录，一个 `[[login]]` 一个 |
| `image/prompt.md`、`image/skills/` | 系统提示和 Wonton 自己的 skill |
| `NOTICE`、许可证文件 | 上游程序、图标来源和商标说明；CLI 的许可证写进清单 `license` |
| `icon.svg` | 首字母图标 |
| `smoke-probes.sh` | 冒烟探针：`web_assert`、`identity_check`、`MCP_TOOL`/`mcp_assert`、`data_write`/`data_check` |
| `docker-compose.yml` | 用 `gen/` 生成后一起提交：`python3 gen/gen.py agents/<id>`（生成器用 PyYAML 解析 agent.yaml，MIT 许可证）。发版写回的自身镜像摘要，版本没变时 gen 原样保留，换了版本就丢掉等发布再写 |

还要实测并在 README 里写明：最严格的模式叫什么、只放行 Wonton MCP 的配置键、内存峰值、越界操作怎么触发确认卡片
（写法见下面「越界操作怎么触发确认卡片」）。这家的差异只放在这个目录里，桥和底座不写特例。

### 越界操作怎么触发确认卡片

Agent 越界动手前的确认卡是 CLI 自己要的：它经 ACP 的 `session/request_permission` 问桥，桥转成核心的
权限确认卡——桥给每个选项编一个 `choice_id`，回答时映射回 ACP 的 optionId——主人答完再转回给 Agent。
（Wonton MCP 工具调用出的卡是核心按自己的工具策略出的，不在这节范围内。）
各家 CLI 什么时候发这个请求差别很大：有的动手前就问，有的先靠自己的沙箱挡、被拒后要模型带着参数重试才升级。
接入新的一家时照实写进这家的 README，并更新下表：

| 家 | 越界操作怎么触发确认卡片 |
| --- | --- |
| [claude-code](agents/claude-code/README.md) | `default` 模式下改文件、跑命令都在执行前出卡，同意才动手 |
| [codex](agents/codex/README.md) | 容器即沙箱（Codex 跑 `danger-full-access`，没有可升级的沙箱）：内置启发式判危的命令、托管规则枚举的写命令、Wonton MCP 工具调用出卡；`apply_patch` 改文件不出卡，越界写由容器边界兜底 |
| [dsh](agents/dsh/README.md) | 不主动出卡：工作区外的操作被沙箱拒绝，工具结果里带 `[sandbox: escalation available …]` 提示，模型按提示带 `sandbox_permissions` + `justification` 重试同一命令才出卡；拒绝则不执行 |
| [kimi-code](agents/kimi-code/README.md) | `default` 模式下动文件、跑命令出权限卡（`approve_once`/`approve_always`/`reject`）；`plan` 模式不执行任何工具 |
| [omp](agents/omp/README.md) | `plan` 档跑命令（exec 档）一律出卡，改工作区先出计划；Wonton MCP 工具（write 档）会话内放行，只出核心自己的工具卡 |
| [opencode](agents/opencode/README.md) | 网关钩子把 `edit`、`shell` 显式写成 `ask`：`plan`、`build` 两档下改文件、跑命令都出卡 |
| [qwen-code](agents/qwen-code/README.md) | 未核实（README 的实测记录还没填） |
| [echo](agents/echo/) | 样例 Agent：无沙箱、不出权限卡 |

## 脚本

脚本都在仓库根，插件目录用 `WONTON_PLUGIN` 指定：

```sh
export WONTON_PLUGIN=agents/codex
scripts/check.sh --official
scripts/dev.sh up
scripts/dev.sh install
scripts/dev.sh smoke
```

`scripts/dev.sh` 的完整用法见脚本头部；状态放在 `.wonton/<目录名>/`，几家可以同时起。升级开发脚本用
`scripts/dev.sh kit-update`（来自 wonton-plugin-template 的提交，版本记在 `scripts/KIT`）。

## 检查

`check.yml` 先按改动的路径算出哪些子目录受影响：改 `base/`、`template/`、`gen/` 或 `scripts/` 就是全部。受影响的
子目录各跑一个作业：`gen --check`、`plugin check`（非官方；官方要求由发布流程发版前的
`--official` 把关）、`shellcheck`、构建 Agent 镜像（不推送）；`base/` 另跑
长度检查、测试和镜像构建。一个子目录失败不影响别的作业。

推 `<id>/v<版本>` 或 `base/v<版本>` 的 tag 触发发布：构建多架构镜像、推送、把摘要写回 compose（底座是 `base/DIGEST`）。
机器人每天读一次 ACP 注册表，注册表上的版本比 `agent.toml` 新时提一个 PR。

## 许可证

本仓库是 Apache-2.0（见 [LICENSE](LICENSE)）。各子目录里上游程序和图标的许可证写在各自的 `NOTICE`。闭源 CLI 不打进
镜像，首次启动时按摘要从官方源下载。
