# Kimi Code 子镜像：底座加配置、网关钩子和订阅登录状态脚本。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.1@sha256:1f66748aa0f30bae92496fabd35bebc35d9fb965762096b876a4b45c1ad2cab2
FROM ${BASE_IMAGE}
COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway acp-launch /usr/local/lib/wonton-agent/
COPY kimi_config.py /usr/local/lib/wonton-agent/kimi_config.py
COPY --chmod=0755 login-status /usr/local/lib/wonton-agent/login-status
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY skills/ /usr/local/share/wonton-agent/skills/
