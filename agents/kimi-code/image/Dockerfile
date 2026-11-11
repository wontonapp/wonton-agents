# Kimi Code 子镜像：底座加 agent.toml、网关钩子和两个登录脚本。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
FROM ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9
COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/gateway
COPY kimi_config.py /usr/local/lib/wonton-agent/kimi_config.py
COPY --chmod=0755 login-platform-key /usr/local/lib/wonton-agent/login-platform-key
COPY --chmod=0755 login-status /usr/local/lib/wonton-agent/login-status
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY skills/ /usr/local/share/wonton-agent/skills/
