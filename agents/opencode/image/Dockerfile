# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
FROM ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9

COPY agent.toml /etc/wonton-agent/
# 登录包装和状态查询一起进 lib；gateway 钩子见 agent.toml 的 [gateway] hook；web-proxy 转发登录网页。
COPY --chmod=0755 gateway opencode-login opencode-auth-status web-proxy /usr/local/lib/wonton-agent/
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
COPY skills/ /usr/local/share/wonton-agent/skills/
