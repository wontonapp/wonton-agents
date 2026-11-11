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
| `docker-compose.yml` | 用 `gen/` 生成后一起提交 |

还要实测并在 README 里写明：最严格的模式叫什么、只放行 Wonton MCP 的配置键、内存峰值。这家的差异只放在这个目录里，
桥和底座不写特例。

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
子目录各跑一个作业：`gen --check`、`plugin check --official`、`shellcheck`、构建 Agent 镜像（不推送）；`base/` 另跑
长度检查、测试和镜像构建。一个子目录失败不影响别的作业。

推 `<id>/v<版本>` 或 `base/v<版本>` 的 tag 触发发布：构建多架构镜像、推送、把摘要写回 compose（底座是 `base/DIGEST`）。
机器人每天读一次 ACP 注册表，注册表上的版本比 `agent.toml` 新时提一个 PR。

## 许可证

本仓库是 Apache-2.0（见 [LICENSE](LICENSE)）。各子目录里上游程序和图标的许可证写在各自的 `NOTICE`。闭源 CLI 不打进
镜像，首次启动时按摘要从官方源下载。
