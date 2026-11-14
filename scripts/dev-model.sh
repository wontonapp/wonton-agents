# shellcheck shell=bash
# shellcheck disable=SC2154 # instance 由 dev.sh 加载设置。
# 由 dev.sh 加载：把一个 OpenAI 兼容的服务商接到本实例的模型网关。
# key 只从文件读，经 stdin 传入容器；宿主命令参数和环境不含 key，但容器内 magpie 的参数可能含 key。
# key 会存进开发环境模型网关的数据目录；只用一次性、限定模型的开发 key，验完在服务商处吊销。
model_upstream() {
  local url="${1:-}" model="${2:-}" key_file="${3:-}" host gateway os container local_host=""
  [[ $# -eq 3 && -n "$model" && -n "${model##*/}" && -n "$key_file" ]] || usage
  [[ "$url" =~ ^https?://[^/[:space:]]+ ]] || die "上游地址要以 http:// 或 https:// 开头：$url"
  [[ -f "$key_file" && -r "$key_file" && -s "$key_file" ]] || die "读不到 key 文件，或它是空的：$key_file"
  need_env
  host="${url#*://}"
  host="${host%%[:/]*}"
  if [[ "$host" == host.docker.internal ]]; then
    os="$(docker info --format '{{.OperatingSystem}}')" || die "查不到 Docker 的运行环境"
    if [[ "$os" != *"Docker Desktop"* && "$os" != *OrbStack* ]]; then
      gateway="$(docker network inspect "wonton-$instance--ai-usemagpie-magpie" \
        --format '{{(index .IPAM.Config 0).Gateway}}')" || die "查询模型网关的插件网络失败"
      [[ -n "$gateway" ]] || die "找不到模型网关的插件网络 wonton-$instance--ai-usemagpie-magpie"
      url="${url/host.docker.internal/$gateway}"
      local_host="$gateway"
    else
      local_host="$host"
    fi
  fi
  container="wonton-$instance--ai-usemagpie-magpie--magpie"
  [[ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null)" == true ]] ||
    die "模型网关容器 $container 不存在或没有运行：看 scripts/dev.sh status"
  # magpie 0.1.1327 的 models= 不接受上游 provider 前缀；默认组由模型网关插件自行同步。
  python3 - "$key_file" "$container" "$url" "${model##*/}" "$SMOKE_CONNECT_TIMEOUT" "$SMOKE_API_MAX_TIME" "$local_host" <<'PY'
import subprocess
import sys

path, container, url, model, connect_timeout, timeout, local_host = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as f:
        key = f.read().strip()
except (OSError, UnicodeError):
    sys.exit("读不到 key 文件，或它不是 UTF-8 文本")
if not key or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key):
    sys.exit("key 文件里应该只有一行非空 key，不能含空白或控制字符")

script = r'''
IFS= read -r key || exit 1
if [ -n "$5" ]; then
  export no_proxy="${no_proxy:+$no_proxy,}$5" NO_PROXY="${NO_PROXY:+$NO_PROXY,}$5"
fi
if ! printf 'Authorization: Bearer %s\n' "$key" | curl --silent --show-error --fail \
  --header @- --output /dev/null --connect-timeout "$3" --max-time "$4" "${1%/}/models"; then
  echo '请求上游模型列表失败：检查网络、地址和 key 的权限' >&2
  exit 1
fi
exec magpie provider add upstream "url=$1" "models=$2" "key=$key"
'''
try:
    result = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c", script, "wonton-model",
         url, model, connect_timeout, timeout, local_host],
        input=(key + "\n").encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
except OSError as e:
    sys.exit(f"无法执行 docker：{e}")
if result.returncode:
    detail = result.stdout.decode("utf-8", errors="replace").replace(key, "[已隐藏]").strip()
    print(f"接模型失败（退出 {result.returncode}）：{detail or 'magpie 没有返回错误详情'}", file=sys.stderr)
    sys.exit(1)
PY
  echo "已向模型网关添加服务商；默认组由网关同步，模型是否可用请另行验证"
}
