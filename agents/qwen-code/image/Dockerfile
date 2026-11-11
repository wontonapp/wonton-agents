# qwen-code 子镜像：qwen-code 0.27.2 是 Apache-2.0 的开源 npm 包（dependencies 为空，解包即用），
# 按摘要打进镜像，容器首启不用再联网下载。官方 npm tgz 按 dist.integrity 的 sha512 核对，不符即失败。
# 入口是底座的 wonton-agent，这里只放 qwen-code 本体、配置、网关钩子和登录脚本。
# 底座按摘要固定，防镜像漂移；底座升级改这一行重新构建。
FROM ghcr.io/wontonapp/wonton-agent-base:0.1.0@sha256:5cba94459910395888a969190420492bd58f88a2928a2f8f9a7deb8b849519e9

ARG QWEN_VERSION=0.27.2
# npm dist.integrity 的 sha512-<base64>。
ARG QWEN_SHA512=0X3lJvQI262mGK3P5iEQiGxu2Zg44aaV3du6Pe/JcWuhwlNeM9/cZF8bIpBhOgaymeSe8az15m//h5MHXHEkew==

USER root
RUN curl --fail --silent --show-error --location --retry 5 --retry-delay 2 --retry-all-errors \
      --speed-limit 10240 --speed-time 30 \
      "https://registry.npmjs.org/@qwen-code/qwen-code/-/qwen-code-${QWEN_VERSION}.tgz" \
      --output /tmp/qwen-code.tgz \
  && python3 -c "import base64, hashlib, sys; want = base64.b64decode('${QWEN_SHA512}').hex(); have = hashlib.sha512(open('/tmp/qwen-code.tgz', 'rb').read()).hexdigest(); sys.exit(f'sha512 不符：{have}' if want != have else 0)" \
  && mkdir -p /usr/local/lib/wonton-agent/qwen-code /usr/share/doc/wonton-qwen-code \
  && tar -xzf /tmp/qwen-code.tgz -C /usr/local/lib/wonton-agent/qwen-code --strip-components=1 \
  && rm /tmp/qwen-code.tgz
USER 65532:65532

COPY agent.toml /etc/wonton-agent/
COPY --chmod=0755 gateway api-key-login api-key-status web-proxy /usr/local/lib/wonton-agent/
COPY qwen_settings.py /usr/local/lib/wonton-agent/
COPY prompt.md /usr/local/share/wonton-agent/prompt.md
# skill 目录 COPY 整棵树：COPY --chmod 会连自动创建的目录一起改（0644 会丢掉目录的 x 位）。
COPY skills/ /usr/local/share/wonton-agent/skills/
COPY LICENSE.qwen-code /usr/share/doc/wonton-qwen-code/LICENSE
