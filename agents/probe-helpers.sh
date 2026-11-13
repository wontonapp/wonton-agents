# shellcheck shell=bash
# agents 各家 smoke-probes.sh 共用的探针助手，由各家用相对自己的路径 source：
#   . "$(dirname "${BASH_SOURCE[0]}")/../probe-helpers.sh"
# 放在 agents/ 不放 scripts/：scripts/ 是开发套件，dev.sh kit-update 按 kit.files 从模板仓库整份覆盖，
# 这里的文件套件不碰。

# Bot 服务的容器：bots.services 里的服务每个 Bot 一组容器，核心给容器名带 `--<Bot 名>` 后缀。
# 名字按 e2e 冒烟套件 e2e_svc 的口径拼：有 --default 就用它，旧核心没有后缀时用裸名。
# data_write / data_check 在装完、重装完马上 exec 进容器，容器可能还在重建，直接 exec 会报
# No such container：所以轮询 docker inspect 等到 running 才返回。上限 180 秒（agent_wait_healthy 的
# 默认值，也在数据钩子 300 秒限时之内），超时报“容器没起来”——数据项如实记失败，不当成 data_write 写错了。
bot_service_container() { # <服务名> → 容器名（状态 running 才返回）
  local base c state
  [[ -n "${SMOKE_INSTANCE:-}" && -n "${SMOKE_SLUG:-}" ]] ||
    { echo "SMOKE_INSTANCE 或 SMOKE_SLUG 没设，拼不出容器名（探针要跑在冒烟套件的环境里）"; return 1; }
  base="wonton-$SMOKE_INSTANCE--$SMOKE_SLUG--$1"
  if docker inspect "$base--default" >/dev/null 2>&1; then c="$base--default"; else c="$base"; fi
  for _ in $(seq 1 90); do
    state="$(docker inspect "$c" --format '{{.State.Status}}' 2>/dev/null)" || state=""
    [[ "$state" == running ]] && { printf '%s\n' "$c"; return 0; }
    sleep 2
  done
  echo "容器没起来：$c 等 180 秒还没 running（docker inspect 现在的状态：${state:-容器不存在}）"
  return 1
}
