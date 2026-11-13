# shellcheck shell=bash
# dsh 只使用 magpie 模型网关，没有登录网页或自己的 MCP 服务。
# 通用探测验证工作区文件重装不丢；附加检查验证加密聊天、模型回答和 Wonton MCP。
export IDENTITY_NA=1
export SMOKE_NOTE="dsh 没有登录网页或应用账号体系；模型只走 magpie，专项检查验证加密聊天和 Wonton MCP。"

# Agent 专项：附加检查里用套件的 Agent 助手逐项记子项（见 scripts/agent-probes.sh）。dsh 默认 workspace-write：
# 工作区里的命令不问，只有改工作区外的文件或出网才出卡片，确认卡片这一项不测。
export EXTRA_TIMEOUT=3000
extra_check() {
  agent_check_chat '请用一句话回答：dsh 冒烟。记住暗号：青杏。'
  agent_check_model
  agent_check_mcp_chat
  agent_check_mcp_bus
  extra_item N/A 确认卡片 "dsh 默认 workspace-write，工作区里的命令不出卡片"
  agent_check_interrupt
  agent_check_restart agent bridge
  agent_check_resume 青杏
  agent_check_outsider
}

# shellcheck source=agents/probe-helpers.sh
. "$(dirname "${BASH_SOURCE[0]}")/../probe-helpers.sh"

_dsh_marker_file() {
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
  printf '%s' "$token" >"$(_dsh_marker_file)" || { echo "写不进标记文件"; return 1; }
}

data_check() {
  local container token out
  container="$(bot_service_container agent)"
  token="$(cat "$(_dsh_marker_file)" 2>/dev/null)" || true
  [[ -n "$token" ]] || { echo "没有 data_write 留下的标记"; return 1; }
  out="$(docker exec "$container" cat /workspace/wonton-smoke-marker 2>/dev/null)" ||
    { echo "标记文件没了：$container:/workspace/wonton-smoke-marker 读不回"; return 1; }
  grep -qF "$token" <<<"$out" || { echo "标记内容对不上：$(head -c 120 <<<"$out")"; return 1; }
  echo "工作区里的标记还在（wonton-smoke $token）"
}
