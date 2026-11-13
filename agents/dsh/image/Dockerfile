# Agent 层：底座镜像（wonton-agent 入口）+ 官方 dsh CLI（@deepseek-ai/dsh，MIT，可再分发，打进镜像）。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.1@sha256:1f66748aa0f30bae92496fabd35bebc35d9fb965762096b876a4b45c1ad2cab2
FROM ${BASE_IMAGE}

# 官方 npm registry 的 tgz，按 npm dist.integrity 校验通过才安装；依赖由 npm 安装时核对。
ARG DSH_VERSION=0.2.2-rc.1
ARG DSH_SHA512=8a347d504558906d7943f43bf49cefccb07340e41f73add52ebf67e9f969c073e1af920a9f6531b619d2a2da3f3fd97ba8677ba4fbc8d516ba4d6ecb1f7a0aa6

# 底座以 USER 65532 收尾，装包要先切 root。
USER root
RUN set -eu \
    && curl --fail --silent --show-error --location --retry 8 --retry-all-errors \
         --continue-at - --retry-delay 3 --max-time 600 \
         "https://registry.npmjs.org/@deepseek-ai/dsh/-/dsh-${DSH_VERSION}.tgz" \
         --output /tmp/dsh.tgz \
    && echo "${DSH_SHA512}  /tmp/dsh.tgz" | sha512sum --check --strict \
    && npm install --prefix /opt/dsh --ignore-scripts --no-audit --no-fund --loglevel=error /tmp/dsh.tgz \
    && rm /tmp/dsh.tgz \
    && /opt/dsh/node_modules/.bin/dsh --version
USER 65532:65532

# dsh 的凭据、会话和 acp profile 补丁都放在数据卷 HOME 下的 .dsh/；遥测全关。
ENV DSH_HOME=/data/agent/home/.dsh \
    DSH_TELEMETRY_MODE=DISABLED

COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/gateway
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY wonton-help/ /usr/local/share/wonton-agent/skills/wonton-help/
COPY LICENSE.dsh /usr/share/doc/wonton-agents/dsh/LICENSE.dsh
