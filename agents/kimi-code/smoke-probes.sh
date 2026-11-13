# shellcheck shell=bash
# Kimi Code 的冒烟探测：登录网页是能直接看的面；Agent 没有用户体系，数据探针写工作区标记。
# 变量和助手（dweb、SMOKE_*）见 scripts/probes.sh 的说明。

web_assert() {
  # 页面是 JS 渲染的：静态 HTML 只有骨架，登录列表从 /api/logins 拿（identity_check 同款助手）。
  grep -q '/api/logins' || { echo "不是底座登录网页（没有 /api/logins）"; return 1; }
  local logins
  logins="$(dweb /api/logins)" || { echo "登录网页 API 打不开：$logins"; return 1; }
  grep -q '"id": "kimi-account"' <<<"$logins" || { echo "列表里没有 kimi-account：$logins"; return 1; }
  grep -q '"id": "platform-key"' <<<"$logins" || { echo "列表里没有 platform-key：$logins"; return 1; }
}

# Agent 没有用户体系：登录网页认的是核心网关的会话。probes.sh 从这份文件读这两个变量。
export IDENTITY_NA=1

# 数据探针：把标记写进 agent 容器的 /workspace（挂的是 ${WONTON_BOT_DATA}/workspace 卷），
# 升级和重装后读回，验证主人给 Agent 的工作区文件不丢。
# shellcheck disable=SC1091 # 助手文件在 agents/ 下，不在 CI 的 shellcheck 输入里；agents/probe-helpers.sh 单独过 shellcheck
. "$(dirname "${BASH_SOURCE[0]}")/../probe-helpers.sh" # 容器定位助手，agents 各家共用

data_write() {
  local id marker
  id="$(bot_service_container agent)" || return 1
  marker="kimi-smoke-$(date +%s)-$RANDOM"
  docker exec "$id" sh -c "printf '%s' '$marker' > /workspace/.wonton-smoke-marker" ||
    { echo "写不进 /workspace"; return 1; }
  printf '%s' "$marker" > "$SMOKE_STATE"
}

data_check() {
  local id marker found
  marker="$(cat "$SMOKE_STATE")"
  id="$(bot_service_container agent)" || return 1
  found="$(docker exec "$id" cat /workspace/.wonton-smoke-marker 2>/dev/null)" ||
    { echo "/workspace/.wonton-smoke-marker 不见了"; return 1; }
  [[ "$found" == "$marker" ]] || { echo "看到 $found，要 $marker"; return 1; }
}
