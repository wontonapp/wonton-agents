# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.2@sha256:032c7ee53bb0ae594c04911ebb1364154c33de9465a5421a4c2f43c166c30849
FROM ${BASE_IMAGE}

COPY agent.toml /etc/wonton-agent/
# gateway 钩子见 agent.toml 的 [gateway] hook。
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
COPY skills/ /usr/local/share/wonton-agent/skills/
