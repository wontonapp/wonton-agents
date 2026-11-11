# 仓库规则

本文件对人和 AI 编程代理（Claude Code、Codex 等）同样适用。通用开发流程见[开发指南](https://github.com/wontonapp/wonton-docs/blob/main/develop.md)，规则见[插件规范](https://github.com/wontonapp/wonton-docs/blob/main/plugin-spec.md)。

## 布局

- 一个仓库放多家 ACP Agent，每家一个 `agents/<id>/`，每个子目录是一个独立插件包。
- 桥和底座只认 ACP 和 `agent.toml`；某家的不同只写在这家的目录里，不改桥、不改底座。
- `agents/<id>/docker-compose.yml` 由 `gen/` 从 `agent.yaml` 和 `template/` 生成，生成结果一起提交；改 `agent.yaml` 后跑生成器，不手改 compose。
- 并发工作时只改自己的 `agents/<id>/`；要改 `base/`、`template/`、`gen/`、`scripts/` 的，单独一个 PR 先合。

## 插件包

- 规则以核心的检查为准：`WONTON_PLUGIN=agents/<id> scripts/check.sh --official` 通过、`scripts/dev.sh install` 装得上，才算写对了。
- 核心不支持插件要的东西时，不绕过规则、不悄悄去掉功能，在 PR 里写明缺什么、为什么，向云吞提 issue。
- 只申请用得到的权限：要出网才申请 `network.egress`，只读的共享文件夹申请 `:read` 并以 `:ro` 挂载。
- 插件网页在核心网关后面，不另建绕过网关的入口；不把用户令牌交给插件。
- 要用大模型就申请 `models`，经模型网关访问。插件里不放第三方 API key，也不让用户把 key 填进插件。
- 插件自己的密钥写在清单 `secrets` 里，由核心生成或保管。
- 镜像用上游官方镜像并按摘要固定；要自己构建的，Dockerfile 放在子目录的 `image/`，由发布工作流构建。新依赖写明许可证（不用 GPL、AGPL）。
- 闭源 CLI 不打进镜像，由底座首次启动时按版本和摘要从官方源下载。

## 质量

- 代码和配置短、清楚、不冗余。每个部分只做一件事；能用上游现有配置做到的，不写脚本，也不加中间层。
- 源码文件 ≤ 800 行，函数 ≤ 100 行；没有用到的代码、配置和依赖删掉。
- 注释只写读代码得不到的信息：为什么这样写、外部系统的实测行为。不写复述代码的注释。
- 公开仓库：注释、README、NOTICE 里不写 ADR 编号（读者看不到）；不写内部主机名和地址，示例用 `192.0.2.10`。

## 运行时原则

- 不用 mock、预览数据、静默降级或兜底掩盖缺失能力。缺配置、依赖没就绪时启动失败或如实报错。
- 错误说清原因：权限缺失、依赖没就绪、上游出错、输入非法，分开说。状态不确定就显示不确定。
- 健康检查检查真正可用，不只是进程活着。

## 界面

- 不加多余的副标题和说明文字，让布局说话；错误、权限和来源的提示照常写清楚。
- 手机竖屏（390×844）要好看。
- 商店信息照规范写：`description` 一句话，`about`、`release_notes` 写清楚。

## 共用一台 Docker

- 开发环境的起停、安装和清理只用 `scripts/dev.sh`，插件目录用 `WONTON_PLUGIN` 指定。
- 不执行 `docker system prune`、`docker container prune` 这类针对整台主机的清理。
- 只动名字里带着自己实例名（`.wonton/` 的 `WONTON_INSTANCE`）的容器、网络和卷。
- 自己构建或拉来试用的镜像，用完按名字删掉；不再开发时执行 `scripts/dev.sh purge`。

## 验证

1. `WONTON_PLUGIN=agents/<id> scripts/check.sh --official` 没有不合格。
2. `scripts/dev.sh reinstall --yes` 装得上，`scripts/dev.sh status` 里是 `running healthy`。
3. 经桥走一轮对话、一次确认卡片、`/wonton login` 列出登录方式；插件网页用一遍。
4. 写进数据的操作做一次，重装以后数据还在；`uninstall --purge` 以后删干净了。

PR 描述写清改了什么、为什么、上面哪几步做了、结果是什么；每个结论附上执行的命令和结果，没做的写明没做。

## Git 与发布

- 只有 `main` 一个长期分支。一件事一个分支、一个 PR。
- 提交信息用 Conventional Commits：`type(scope): 中文摘要`，`type` 取 `feat`、`fix`、`docs`、`refactor`、`chore`、`build`、`ci`。
- 不提交 `.wonton/`、密钥和调试产物（截图、日志）。截图只有商店用的放在子目录的 `screenshots/`。
- 发布：改 `agent.yaml` 的 `version`、写好 `release_notes`、重新生成 compose、提交，再推 `<id>/v<版本>` 的 tag。
- 提交作者用 GitHub 的 noreply 邮箱：`git config user.email "<数字 ID>+<用户名>@users.noreply.github.com"`。
