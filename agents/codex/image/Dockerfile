# codex 的子镜像：底座之上的全部差异是 COPY 进来的几样，再加打进镜像的开源 CLI。
# Codex CLI 和 ACP 适配器都是 Apache-2.0 的开源 npm 包，按底座对开源 CLI 的路子直接
# 打进镜像（运行时不用下载，首启不依赖出网）；版本和摘要固定在下面，升级改这里。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。BASE_IMAGE 只给本地开发
# 覆盖用（发布构建不带这个参数，走上面的固定摘要）。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9
FROM ${BASE_IMAGE}

ARG CODEX_ACP_VERSION=2.6.0
# npm dist.integrity 的 sha512，展开成十六进制校验（registry.npmjs.org 的 2.6.0 元数据）。
# 适配器依赖 @openai/codex ^0.166.0，包里没有 npm-shrinkwrap.json，CLI 版本跟着 semver 走；
# 升级时按注册表机器人的 PR 重取版本和摘要。
ARG CODEX_ACP_SHA512=fcf06c7741fa511cb86e15e101e5eac1bed1a9cb5b5df35c7918a1021ea70e69f91c9f3bdeece81ef1f1178e5899e59f80e28a46b3512d98d8b247add9aec4b1

USER root
# 下载、解包、装依赖各占一层：重跑只重来失败的一步。npm 慢或抖的网络上
# curl 带断点重试，npm 加大重试和超时。
RUN set -eu \
    && curl --fail --silent --show-error --location --retry 8 --retry-all-errors \
         --continue-at - --retry-delay 3 --max-time 600 \
         "https://registry.npmjs.org/@agentclientprotocol/codex-acp/-/codex-acp-${CODEX_ACP_VERSION}.tgz" \
         --output /tmp/codex-acp.tgz \
    && echo "${CODEX_ACP_SHA512}  /tmp/codex-acp.tgz" | sha512sum --check --strict \
    && mkdir -p /opt/codex-acp \
    && tar -xzf /tmp/codex-acp.tgz -C /opt/codex-acp --strip-components=1 \
    && rm /tmp/codex-acp.tgz
RUN npm install --prefix /opt/codex-acp --ignore-scripts --no-audit --no-fund --loglevel=error \
    --fetch-retries 8 --fetch-retry-maxtimeout 90000 --fetch-timeout 600000 \
    && test -d /opt/codex-acp/node_modules/@openai/codex-linux-x64 \
    && test -x /opt/codex-acp/node_modules/@openai/codex-linux-x64/vendor/*/bin/codex
# 平台包是 optionalDependencies：npm 装失败不报错，codex.js 运行时才炸，必须在构建期拦住。
USER 65532:65532

COPY agent.toml /etc/wonton-agent/
# 容器即沙箱的托管约束（模式限制 + 写命令确认规则），见文件头注释和 README。
COPY requirements.toml /etc/codex/requirements.toml
# 底座 0.1.0 还没有 web 服务的转发器（base 的修复 PR 合了以后这行和文件删掉），
# qwen-code 同款：自足的 TCP 字节搬运，SSE 不缓冲。
COPY --chmod=0755 gateway web-proxy /usr/local/lib/wonton-agent/
# Codex 对目录外的模型要求完整模型元数据：这份 prompt.md（Codex 上游对未知模型的
# 兜底指令）由网关钩子写进 model_catalog_json 的 base_instructions，见 NOTICE。
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY skills/ /usr/local/share/wonton-agent/skills/
