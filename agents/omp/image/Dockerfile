# omp 的 Agent 层：公共底座加官方二进制和这份配置。omp 是开源 CLI（MIT），直接打进镜像。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
ARG BASE_IMAGE=ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9
FROM ${BASE_IMAGE}

ARG TARGETARCH
# 上游只在 GitHub Releases 发二进制，没有官方镜像；按版本和 SHA-256 固定（上游 SHA256SUMS.txt），不自己编。
ARG OMP_VERSION=18.16.0
ARG OMP_X64_SHA256=6498ed785bab00d2926e0387e0ec02362d6d45f1c3d0d1b57c1618b7f95c9264
ARG OMP_ARM64_SHA256=c2be1ea85ce17c4270854b57efff2a7ea1d5a03c7557fd08721f2b9bb32698de

USER root
# 上游只在 GitHub Releases 发二进制，没有官方镜像；按版本和 SHA-256 固定（上游 SHA256SUMS.txt），不自己编。
# 文件 277 MB，从部分网络环境下载会反复断流：同一个 RUN 里循环续传（-C -），30 次机会，
# 每次低于 10 KB/s 超 30 秒按失败算，最终仍以 sha256 --check --strict 把关，下不完整就装不上。
RUN case "$TARGETARCH" in \
      amd64) asset=omp-linux-x64; checksum="$OMP_X64_SHA256" ;; \
      arm64) asset=omp-linux-arm64; checksum="$OMP_ARM64_SHA256" ;; \
      *) echo "不支持的架构 $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && ok=0 \
    && for _ in $(seq 1 30); do \
         curl --fail --silent --show-error --location -C - \
              --connect-timeout 15 --speed-limit 10240 --speed-time 30 \
              "https://github.com/can1357/oh-my-pi/releases/download/v${OMP_VERSION}/${asset}" \
              --output /usr/local/bin/omp && ok=1 && break; \
         sleep 2; \
       done \
    && [ "$ok" = 1 ] \
    && echo "$checksum  /usr/local/bin/omp" | sha256sum --check --strict \
    && chmod 0755 /usr/local/bin/omp \
    && mkdir -p /usr/share/doc/wonton-omp
USER 65532:65532

COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway /usr/local/lib/wonton-agent/gateway
COPY skills/ /usr/local/share/wonton-agent/skills/
COPY LICENSE.omp /usr/share/doc/wonton-omp/LICENSE
