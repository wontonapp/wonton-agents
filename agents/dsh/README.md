# dsh

DeepSeek 的 dsh（DeepSeek Harness）住在云吞里：官方 npm 包 `@deepseek-ai/dsh`（MIT，打进镜像）经它自带的
`--profile acp` 说 ACP，用核心分配的 Matrix 身份和主人聊天，工具经 Wonton MCP 总线来。模型网关接好时默认走
网关，不用账号、也不用填 key；没接网关时 Agent 照常启动，在聊天里发 `/wonton login`（这个聊天对应的 Bot）
或从插件页打开登录网页（默认 Bot），贴一个自己的 DeepSeek API key（platform.deepseek.com 创建）。登录态存在
数据目录的 `.credentials.yaml`（0600），容器重建后还在；网关接入或卸掉后重启容器即切换。

dsh 的会话日志和遥测默认回传上游，插件把它关了（`DSH_TELEMETRY_MODE=DISABLED`；无论走网关还是
用户自己的 key，都关掉 `session-log-deepseek` 插件，会话日志不出容器）。

## 实测记录

| 项 | 值 |
| --- | --- |
| 最严格的模式 | `workspace-write`（dsh 沙箱预设；`read-only` 下工具几乎全被拒，不可用） |
| 只放行 Wonton MCP 的配置键 | 不需要配置键：dsh 自己的配置（cordis.yml）默认不带任何 MCP 服务器，Wonton MCP 只经桥在 `session/new` 的 `mcpServers` 传入（dsh 的 ACP 声明 `mcpCapabilities.http`，直接挂 HTTP 总线；实测工具列表含 `mcp__wonton__*`） |
| 内存峰值 | agent 容器 263 MiB（多轮对话中采样，含一次沙箱升级请求），bridge 10 MiB；清单 1G 余量充足 |

dsh 的 ACP 不声明会话模式（`session/set_mode` 和模式类 `configOptions` 都没有），桥按 ACP 规范跳过切换
（桥 ≥0.2.1；更早的桥会对 dsh 发 `session/set_mode` 并被拒，会话建不起来）。沙箱预设固定为 dsh 自己的
默认 `workspace-write`：工作区内自由读写，`/tmp` 等平台临时区放行；工作区外的文件操作被沙箱拒绝并在
结果里提示升级，模型带 `sandbox_permissions` + `justification` 重试同一命令时才弹确认卡片，拒绝则不执行。

## 构建镜像

```sh
docker build -t ghcr.io/wontonapp/wonton-agents/dsh:<版本> agents/dsh/image
```

底座按摘要固定在 `image/Dockerfile` 的 FROM；底座升级改那一行重新构建。

## 图标

`icon.svg` 是按插件规范手绘的线条图标（小写 d 字形），原创。DeepSeek 和 dsh 是 DeepSeek 的商标；本插件不是
DeepSeek 的官方出品。来源、上游程序和许可证的说明见 [NOTICE](NOTICE)。
