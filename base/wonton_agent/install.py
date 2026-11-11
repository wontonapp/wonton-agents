"""[[install]] 按需安装闭源 CLI：首次启动从官方源下载到数据卷的版本目录，摘要核对通过才落盘。
闭源 CLI 不打进发布的镜像（要跟官方源、按版本和摘要核对）。"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from . import log
from .config import NPM_REGISTRY, parse_integrity

TOOLS_ROOT = Path("/data/agent/tools")


def current_arch() -> str:
    return {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())


def verify_digest(item_name: str, path: Path, algo: str, expected_hex: str) -> None:
    actual = hashlib.new(algo, path.read_bytes()).hexdigest()
    if actual != expected_hex.lower():
        raise RuntimeError(
            f"安装 {item_name}：下载文件摘要不符，期望 {algo}:{expected_hex.lower()}，实际 {algo}:{actual}。"
            "可能是上游改了文件或下载被调包，拒绝安装。")


def download(url: str, target: Path) -> None:
    # 代理由核心注入（HTTPS_PROXY 等环境变量），urllib 自己遵守，不另写代理。
    request = urllib.request.Request(url, headers={"User-Agent": "wonton-agent"})
    with urllib.request.urlopen(request) as response, open(target, "wb") as file:
        shutil.copyfileobj(response, file)


def npm_install(prefix: Path) -> None:
    # --ignore-scripts：不执行包里的安装脚本。npm 读容器里的代理变量出网。
    result = subprocess.run(
        ["npm", "install", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund",
         "--loglevel=error"],
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"npm install --prefix {prefix} 失败（退出码 {result.returncode}），看上面日志")


def install_tools(config: dict) -> None:
    for item in config.get("install", []):
        name, version = item["name"], item["version"]
        final = TOOLS_ROOT / name / version
        if final.is_dir():
            log(f"安装 {name}：{version} 已在 {final}，跳过下载")
            continue
        for stale in TOOLS_ROOT.glob(f".{name}-*.download-*"):
            shutil.rmtree(stale, ignore_errors=True)
        staging = TOOLS_ROOT / f".{name}-{version}.download-{os.getpid()}"
        staging.mkdir(parents=True)
        try:
            if item["source"] == "npm":
                install_npm_package(item, staging)
            else:
                install_url_package(item, staging)
            final.parent.mkdir(parents=True, exist_ok=True)
            staging.rename(final)
            log(f"安装 {name}：{version} 装到 {final}")
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def strip_dev_dependencies(package_json: Path, name: str) -> None:
    # devDependencies 是 CLI 仓库的构建期依赖，官方包常在这里引用未发布的内部包
    # （实测 kimi-code 2.5.3 的 @moonshot-ai/acp-server 就是 404），装它们只会失败；
    # 运行只认 dependencies，CLI 本体是打进包里的 bundle，不依赖这些包。
    try:
        manifest = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"安装 {name}：package.json 读不出来（{error}）") from error
    if isinstance(manifest, dict) and manifest.pop("devDependencies", None) is not None:
        package_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def install_npm_package(item: dict, staging: Path) -> None:
    name, package = item["name"], item["package"]
    filename = package.split("/")[-1]
    registry = item.get("registry", NPM_REGISTRY).rstrip("/")
    url = f"{registry}/{package}/-/{filename}-{item['version']}.tgz"
    archive = staging / "package.tgz"
    log(f"安装 {name}：从 {url} 下载 npm 包")
    download(url, archive)
    algo, expected = parse_integrity(item["integrity"])
    verify_digest(name, archive, algo, expected)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            # filter="data"：拒绝包内路径穿越和特殊权限位。
            tar.extractall(staging, filter="data")
    except tarfile.TarError as error:
        raise RuntimeError(f"安装 {name}：下载的 npm 包不是合法 tgz（{error}）") from error
    extracted = staging / "package"
    if not (extracted / "package.json").is_file():
        raise RuntimeError(f"安装 {name}：npm 包里没有 package/package.json，不是合法的包")
    for child in extracted.iterdir():
        shutil.move(str(child), staging / child.name)
    extracted.rmdir()
    archive.unlink()
    strip_dev_dependencies(staging / "package.json", name)
    npm_install(staging)


def install_url_package(item: dict, staging: Path) -> None:
    name, arch = item["name"], current_arch()
    url = item[f"url_{arch}"]
    basename = url.rsplit("/", 1)[-1].split("?", 1)[0] or "download.bin"
    archive = staging / basename
    log(f"安装 {name}：从 {url} 下载 {arch} 构建")
    download(url, archive)
    verify_digest(name, archive, "sha256", item[f"sha256_{arch}"])
    if item.get("format", "binary") == "tgz":
        try:
            with tarfile.open(archive, "r:*") as tar:
                tar.extractall(staging, filter="data")
        except tarfile.TarError as error:
            raise RuntimeError(f"安装 {name}：下载的文件不是合法 tar 包（{error}）") from error
        archive.unlink()
    else:
        archive.chmod(0o755)
