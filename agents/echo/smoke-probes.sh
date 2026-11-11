# shellcheck shell=bash
# Echo 的冒烟探测：登录网页是样例唯一能看的面；不存用户数据，身份也只在网关会话里。
# 变量和助手（dweb、SMOKE_*）见 scripts/probes.sh 的说明。

web_assert() { grep -qF '登录成功，Agent 正在重启'; }

# 登录网页没有用户体系：认出的是核心网关的会话，不是 Echo 里的身份。probes.sh 从这份文件读这两个变量。
export IDENTITY_NA=1
export SMOKE_NOTE="Echo 没有用户体系，登录网页只认核心网关的会话。"

# 样例不存用户数据（样例登录只写一个标记文件，重装丢了也无妨）。
export DATA_NA=1
