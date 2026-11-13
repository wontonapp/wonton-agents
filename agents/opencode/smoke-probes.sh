# opencode 是 Agent：没有应用账号体系或插件自己的 MCP 服务；清单有 webui（登录网页）。
# shellcheck shell=bash disable=SC2034
# 通用插件冒烟只验证清单能装上；Matrix 加密私聊、模型回答和 Wonton MCP 在专项验收里实测。
IDENTITY_NA=1
SMOKE_NOTE="opencode 没有应用账号体系或插件自己的 MCP 服务，登录网页登的是 OpenCode 官方账号；主人身份、插件工具两项不适用。专项验收验证加密 Matrix 私聊、模型回答和 Wonton MCP 只读工具。"

web_assert() { # 标准输入：登录网页（底座 wonton-agent 的登录页，经 web 服务转发）。
  # 只用一个 grep：web_assert 的标准输入只能读一遍（两个 grep 会把第二趟读成空）。
  grep -q '云吞页面令牌'
}

# 数据：Agent 的工作区文件和登录态会话之间一直在用（docker-compose.yml 的 ${WONTON_BOT_DATA}/workspace、agent 卷）。
# data_write 在 agent 容器的工作区落一个标记文件，data_check 在升级、重装后读回比对；内容带随机令牌。
# shellcheck disable=SC1091 # 助手文件在 agents/ 下，不在 CI 的 shellcheck 输入里；agents/probe-helpers.sh 单独过 shellcheck
. "$(dirname "${BASH_SOURCE[0]}")/../probe-helpers.sh" # 容器定位助手，agents 各家共用

_oc_marker_file() { # 标记文件：SMOKE_STATE 在 dev.sh probes 里是目录，目录里放标记文件
  if [[ -d "${SMOKE_STATE:-}" ]]; then printf '%s/data-marker' "$SMOKE_STATE"; else printf '%s' "${SMOKE_STATE:-}"; fi
}

data_write() {
  local container token out
  container="$(bot_service_container agent)"
  token="wonton-smoke-$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
  docker exec "$container" sh -c "printf 'wonton-smoke %s\n' '$token' > /workspace/wonton-smoke-marker" ||
    { echo "往 $container:/workspace 写标记失败"; return 1; }
  out="$(docker exec "$container" cat /workspace/wonton-smoke-marker)" || { echo "标记写完读不回"; return 1; }
  grep -qF "$token" <<<"$out" || { echo "标记读回对不上：$out"; return 1; }
  printf '%s' "$token" >"$(_oc_marker_file)" || { echo "写不进标记文件"; return 1; }
}

data_check() {
  local container token out
  container="$(bot_service_container agent)"
  token="$(cat "$(_oc_marker_file)" 2>/dev/null)" || true
  [[ -n "$token" ]] || { echo "没有 data_write 留下的标记（SMOKE_STATE=${SMOKE_STATE:-未设置}）"; return 1; }
  out="$(docker exec "$container" cat /workspace/wonton-smoke-marker 2>/dev/null)" ||
    { echo "标记文件没了：$container:/workspace/wonton-smoke-marker 读不回"; return 1; }
  grep -qF "$token" <<<"$out" || { echo "标记内容对不上：$(head -c 120 <<<"$out")"; return 1; }
  echo "工作区里的标记还在（wonton-smoke $token）"
}
