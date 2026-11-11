# shellcheck shell=bash
# codex 的冒烟探测：看得见的面是登录网页（列两种官方登录和状态）；身份认的是核心网关
# 的会话，不是 Codex 自己的账号体系。变量和助手（dweb、SMOKE_*）见 scripts/probes.sh 的说明。

# 登录网页列出两种登录方式：页面是 JS 渲染的，列表走 /api/logins 接口。
web_assert() {
  local json
  json="$(web_get /api/logins)" || return 1
  grep -qF 'chatgpt' <<<"$json" && grep -qF 'api-key' <<<"$json"
}

# 登录网页没有用户体系：认出的是核心网关的会话，不是 Codex 的账号。probes.sh 从这份
# 文件读这两个变量。
export IDENTITY_NA=1
export SMOKE_NOTE="Codex 没有应用账号体系，登录网页只认核心网关的会话。"

# 数据：Codex 的工作区文件会话之间一直在用（docker-compose.yml 的
# ${WONTON_BOT_DATA}/workspace:/workspace）。data_write 在 agent 容器的工作区落一个
# 标记文件，data_check 在升级、重装后读回比对；内容带随机令牌。
_cx_container() { printf 'wonton-%s--%s--agent--default' "${SMOKE_INSTANCE:-}" "${SMOKE_SLUG:-ai-codex}"; }

_cx_marker_file() { # 标记文件：SMOKE_STATE 是 probes.sh 建的空文件，标记令牌记进去
  printf '%s' "${SMOKE_STATE:-}"
}

data_write() {
  local container token out
  container="$(_cx_container)"
  token="wonton-smoke-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
  docker exec "$container" sh -c "printf 'wonton-smoke %s\n' '$token' > /workspace/wonton-smoke-marker" ||
    { echo "往 $container:/workspace 写标记失败"; return 1; }
  out="$(docker exec "$container" cat /workspace/wonton-smoke-marker)" || { echo "标记写完读不回"; return 1; }
  grep -qF "$token" <<<"$out" || { echo "标记读回对不上：$out"; return 1; }
  printf '%s' "$token" >"$(_cx_marker_file)" || { echo "写不进标记文件"; return 1; }
}

data_check() {
  local container token out
  container="$(_cx_container)"
  token="$(cat "$(_cx_marker_file)" 2>/dev/null)" || true
  [[ -n "$token" ]] || { echo "没有 data_write 留下的标记（SMOKE_STATE=${SMOKE_STATE:-未设置}）"; return 1; }
  out="$(docker exec "$container" cat /workspace/wonton-smoke-marker 2>/dev/null)" ||
    { echo "标记文件没了：$container:/workspace/wonton-smoke-marker 读不回"; return 1; }
  grep -qF "$token" <<<"$out" || { echo "标记内容对不上：$(head -c 120 <<<"$out")"; return 1; }
  echo "工作区里的标记还在（wonton-smoke $token）"
}
