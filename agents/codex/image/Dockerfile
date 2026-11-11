# codex 的子镜像：只写这家躲不开的几样，其余全在 wonton-agent-base 底座里。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
FROM ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9
COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/gateway
# Codex 对目录外的模型要求完整模型元数据：这份 prompt.md（Codex 上游对未知模型的
# 兜底指令）由网关钩子写进 model_catalog_json 的 base_instructions，见 NOTICE。
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY skills/ /usr/local/share/wonton-agent/skills/
