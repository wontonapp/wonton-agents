# shellcheck shell=bash
# omp 的冒烟探测：omp 没有自己的网页和账号体系（登录走聊天里的 /wonton login），身份认的
# 是核心网关的会话。变量和助手（SMOKE_*）见 scripts/probes.sh 的说明。

# 登录没有独立网页：主会话里发 /wonton login，方式列表和链接由桥发进聊天，冒烟里由人核对。
export IDENTITY_NA=1
export SMOKE_NOTE="omp 没有自己的用户体系；登录态存在 agent 容器的数据卷里。"

# 数据探针把标记写进 agent 容器的数据卷（HOME，agent.db 和会话也在那里），验证重装不丢。
agent_exec() {
  docker exec "wonton-$SMOKE_INSTANCE--${SMOKE_PLUGIN_ID//./-}--agent" "$@"
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
