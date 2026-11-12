# shellcheck shell=bash
# dsh 的冒烟探测：网页是登录页（贴 DeepSeek API key，sso: none，网关挡在前面），没有自己的 MCP 服务。
# 通用插件冒烟验证装得上、登录页打得开、登录态（凭据文件里的 key）重装不丢；
# Matrix 加密私聊、模型回答和 Wonton MCP 工具在附加检查里实测。
export IDENTITY_NA=1
export SMOKE_NOTE="dsh 的网页是登录页，没有应用账号体系，主人身份由核心网关保证；没有自己的 MCP 服务。附加检查验证加密 Matrix 私聊、模型回答和 Wonton MCP 工具。"

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
  agent_check_login_web api-key
  agent_check_login api-key '输入|粘贴|enter|key'
  agent_check_outsider
}

# 登录页的固定特征：agent 底座的静态页，标题就是「登录」。
web_assert() { grep -q '<title>登录</title>'; }

# 数据 = 登录态。走登录网页自己的接口写一个随机 key（dsh-login 收一行写进凭据文件），
# 重装后登录状态命令（dsh-login-status 读同一个文件）还认它，登录态才算保住。
logins_get() { web_get /api/logins; }

dsh_login_id() { # 清单里只有一个 [[login]]
  local res
  res="$(logins_get)" || { echo "拿不到登录列表：$res"; return 1; }
  jq -er '.logins[0].id // empty' <<<"$res"
}

data_write() {
  local id res key st
  id="$(dsh_login_id)" || return 1
  key="x-wonton-smoke-$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  res="$(web_get "/api/logins/$id/start" -X POST -H 'Content-Type: application/json' --data '{}')" ||
    { echo "起登录失败：$res"; return 1; }
  res="$(web_get "/api/logins/$id/input" -X POST -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg t "$key" '{text:$t}')")" || { echo "发送 key 失败：$res"; return 1; }
  # key 保存后 Agent 按新登录态重启，网页跟着重启，状态要等一会儿才查得到。
  for _ in $(seq 1 60); do
    if res="$(logins_get)"; then
      st="$(jq -r --arg id "$id" '.logins[] | select(.id == $id) | .status' <<<"$res")"
      [[ "$st" == logged_in ]] && return 0
    fi
    sleep 2
  done
  echo "登录没在 120 秒内变成 logged_in：$(jq -c --arg id "$id" '[.logins[] | select(.id == $id)]' <<<"${res:-空}")"
  return 1
}

data_check() {
  local id res st detail
  id="$(dsh_login_id)" || return 1
  res="$(logins_get)" || { echo "重装后拿不到登录列表：$res"; return 1; }
  st="$(jq -r --arg id "$id" '.logins[] | select(.id == $id) | .status' <<<"$res")"
  [[ "$st" == logged_in ]] ||
    { detail="$(jq -r --arg id "$id" '.logins[] | select(.id == $id) | .detail // "无详情"' <<<"$res")";
      echo "重装后登录项状态是 $st（要 logged_in），详情：$detail"; return 1; }
}
