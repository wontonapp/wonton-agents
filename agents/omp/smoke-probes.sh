# shellcheck shell=bash
# omp 的冒烟探测：omp 没有自己的网页和账号体系（登录走聊天里的 /wonton login），身份认的
# 是核心网关的会话。变量和助手（SMOKE_*）见 scripts/probes.sh 的说明。

# 登录没有独立网页：人工核对 /wonton login 只列官方订阅方式和 magpie，没有泛用 provider/key 选单。
# 在一次性数据卷验证：未选择订阅且网关缺配置时报告未就绪；选择订阅后不自动切回网关；选择 magpie 后恢复网关。
# 不把已保存的 token/key 当作模式选择，也不在常规冒烟中进行真实订阅授权。
export IDENTITY_NA=1
export SMOKE_NOTE="omp 默认使用 magpie；官方订阅须从 /wonton login 明确选择，不提供模型 key 登录。"

# Agent 的附加检查（助手见开发套件的 scripts/agent-probes.sh）：首条消息留暗号，重启 agent 和 bridge 以后同一个会话
# 还要问得回来。一轮十几条消息、每条要等模型，放宽到 50 分钟。
export EXTRA_TIMEOUT=3000
export AGENT_CARD_REQUIRED=1
extra_check() {
  agent_check_chat '请用一句话回答：omp 冒烟。记住暗号：青杏。'
  agent_check_model
  agent_check_mcp_chat
  agent_check_mcp_bus
  agent_check_card
  agent_check_interrupt
  agent_check_restart agent bridge
  agent_check_resume 青杏
  agent_check_outsider
}

# 数据探针把标记写进 agent 容器的数据卷（HOME，agent.db 和会话也在那里），验证重装不丢。
# shellcheck disable=SC1091 # 助手文件在 agents/ 下，不在 CI 的 shellcheck 输入里；agents/probe-helpers.sh 单独过 shellcheck
. "$(dirname "${BASH_SOURCE[0]}")/../probe-helpers.sh" # 容器定位助手，agents 各家共用

agent_exec() {
  local container
  container="$(bot_service_container agent)" || return 1
  docker exec "$container" "$@"
}

data_write() {
  local marker
  marker="probe-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')"
  agent_exec sh -c "printf %s '$marker' > /data/agent/home/.wonton-probe" ||
    { echo "写不进 agent 容器的数据卷"; return 1; }
  printf %s "$marker" >"$SMOKE_STATE"
}

data_check() {
  local got
  got="$(agent_exec cat /data/agent/home/.wonton-probe 2>&1)" ||
    { echo "读不回标记：$got"; return 1; }
  [[ "$got" == "$(cat "$SMOKE_STATE")" ]] || { echo "标记对不上：读到 $got"; return 1; }
}
