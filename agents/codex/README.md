# Codex

OpenAI Codex 作为 Bot 住进聊天。这一目录是它自己的差异：`agent.yaml`（清单）、
`image/`（`agent.toml`、网关钩子、登录、提示词、skill、托管约束）、`NOTICE`、图标和
冒烟探针。桥、底座和 compose 由仓库共用，不在这里。

## 容器即沙箱

Codex 0.166 自带的沙箱在普通 Docker 容器里起不来：受限模式（read-only、
workspace-write）的命令要靠 bubblewrap 建 user namespace，Docker 默认 seccomp 禁止
容器里建 namespace，宿主内核又常开着 `apparmor_restrict_unprivileged_userns`；退回
Landlock 的开关（`use_legacy_landlock`）在 0.166 遇到受限文件系统策略会直接拒绝启动
沙箱（`linux-sandbox/src/linux_run_main.rs` 的显式检查）。官方文档对这种部署的建议
是：容器提供隔离，Codex 用 `danger-full-access` 跑（codex `docs/sandbox.md`：
「we recommend configuring your Docker container so that it provides the sandbox
guarantees you are looking for and then running codex with --sandbox
danger-full-access」，https://github.com/openai/codex/blob/459363e17b4491f5f06af5d56ef60186746fbf80/docs/sandbox.md ）。

本插件照这个思路做，边界由容器给出：

- **容器本身**：底座以 uid 65532 跑、没有任何 Linux 能力（CapEff 0）、没有 Docker
  socket、只挂工作区和数据卷。写 `/root`、`/etc` 一律 Permission denied；数据卷外的
  写（`/tmp` 等）容器重建就消失。Codex 里声明 `sandbox_mode =
  "danger-full-access"`（网关钩子写进 config.toml），不再依赖 landlock/bwrap。
- **确认卡片**（`/etc/codex/requirements.toml` 托管约束）：默认档 `approval_policy =
  "on-request"`——命令不问就跑；Codex 内置启发式判为危险的命令（`rm -rf` 之类）出
  卡片；写文件的常用命令（touch、mkdir、rm、mv、cp、tee、chmod、sed、curl、wget
  等，全表见 requirements.toml）由 execpolicy 规则出卡片；Wonton MCP 工具的调用出
  卡片。改文件走 `apply_patch` 工具或未枚举的写法（如 `bash -c 'echo > f'`）不出
  卡片，如实说：这是 0.166 下能做到的边界，规则只认命令前缀。
- **ACP 模式**：初始和可用档是托管 profile `wonton-container`（ACP 模式 id
  `permission-profile:wonton-container`）。面板里另有 Codex 自带的 read-only /
  workspace-write / agent / full access 四档：前三档的沙箱在容器里起不来（命令一律
  失败退出，报 bwrap 的 namespace 错误），full access 与本容器档等价但不带确认
  规则；挑它们不如留在容器档。

## 实测记录（0.1.0，Codex CLI 0.166.0 + codex-acp 2.6.0）

| 场景 | 配置 | 结果 |
| --- | --- | --- |
| 安全读命令（echo、ls） | 容器档 + on-request | 不问直接跑 |
| 写命令（touch，无规则时） | 同上 | 不问直接跑（容器边界兜底） |
| 写命令（touch，requirements 有 prompt 规则） | 同上 | 出确认卡片，文件等答复后才写 |
| 危险命令（`rm -rf`，无规则） | 同上 | Codex 内置启发式出卡片 |
| apply_patch 改文件 | 同上 | 不出卡片（0.166 的 approval 跟着沙箱升级走，容器档没有可升级的沙箱） |
| Wonton MCP 工具调用 | 同上 | 出卡片，允许/拒绝都验证过 |
| 面板挑 read-only / workspace-write / agent | 同上 | set_mode 被接受，但命令一律失败退出（bwrap namespace 报错） |
| 面板挑 full access | 同上 | 等价容器档，但不带写命令确认规则 |
| /root 读写 | 容器边界 | Permission denied |
| docker.sock | 容器边界 | 不存在 |
| `/tmp` 写后重建容器 | 容器边界 | 文件消失 |
| `/workspace`（数据卷）写后重装 | 容器边界 | 文件还在（冒烟探针验证） |

内存峰值：agent 容器 cgroup `memory.peak` 102 MiB（一轮对话 + 一次确认，适配器与
app-server 同容器）；桥 11 MiB。agent.yaml 声明 1G。

## 模型和登录

模型网关接好时（三个 `WONTON_MODEL_*` 都有值），网关钩子把网关写进
`$CODEX_HOME/config.toml`：`model_provider`、`model`、`model_catalog_json` 和
`[model_providers.wonton]`；API key 只以 `env_key = "OPENAI_API_KEY"` 引用变量名，
值由底座经 `[gateway.env]` 注进 ACP 子进程。任一变量为空时钩子清掉网关配置，
改用官方登录态；容器即沙箱的声明和 on-request 档两种情况下都保留。

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
