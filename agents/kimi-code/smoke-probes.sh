# shellcheck shell=bash
# Kimi Code 的冒烟探测：登录网页是能直接看的面；Agent 没有用户体系，数据探针写工作区标记。
# 变量和助手（dweb、SMOKE_*）见 scripts/probes.sh 的说明。

web_assert() { grep -qF 'Kimi'; }

# Agent 没有用户体系：登录网页认的是核心网关的会话。probes.sh 从这份文件读这两个变量。
export IDENTITY_NA=1

# 数据探针：把标记写进 agent 容器的 /workspace（挂的是 ${WONTON_BOT_DATA}/workspace 卷），
# 升级和重装后读回，验证主人给 Agent 的工作区文件不丢。
_container() { # <服务名>：本实例里这个服务的容器（按核心打的标签找，见插件模板的说明）
  local inst="${SMOKE_INSTANCE:-}" args=(--filter "label=wonton.plugin=$SMOKE_PLUGIN_ID" --filter "label=wonton.service=$1")
  if [[ -z "$inst" && -n "${SMOKE_BASE:-}" ]]; then
    inst="${SMOKE_BASE#http://}"; inst="${inst%%.*}"
  fi
  [[ -z "$inst" ]] || args+=(--filter "label=wonton.instance=${inst//-/}")
  docker ps --format '{{.Names}}' "${args[@]}" | head -1
}

data_write() {
  local id marker
  id="$(_container agent)" || { echo "没有在跑的 agent 容器"; return 1; }
  marker="kimi-smoke-$(date +%s)-$RANDOM"
  docker exec "$id" sh -c "printf '%s' '$marker' > /workspace/.wonton-smoke-marker" ||
    { echo "写不进 /workspace"; return 1; }
  printf '%s' "$marker" > "$SMOKE_STATE"
}

data_check() {
  local id marker found
  marker="$(cat "$SMOKE_STATE")"
  id="$(_container agent)" || { echo "没有在跑的 agent 容器"; return 1; }
  found="$(docker exec "$id" cat /workspace/.wonton-smoke-marker 2>/dev/null)" ||
    { echo "/workspace/.wonton-smoke-marker 不见了"; return 1; }
  [[ "$found" == "$marker" ]] || { echo "看到 $found，要 $marker"; return 1; }
}
