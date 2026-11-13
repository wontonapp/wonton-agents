# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.1@sha256:1f66748aa0f30bae92496fabd35bebc35d9fb965762096b876a4b45c1ad2cab2
FROM ${BASE_IMAGE}

COPY agent.toml /etc/wonton-agent/
# gateway 钩子见 agent.toml 的 [gateway] hook。
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
COPY skills/ /usr/local/share/wonton-agent/skills/
