"""make init dev|prod: 產生 .env、檢查環境, 開發機另外安裝相依。

已經有 .env 時不覆寫任何值, 只補上 .env.example 新增的變數。
"""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import sys

from tools.env import ENV_EXAMPLE, ENV_FILE, REPO_ROOT, fail, parse_env_file

USAGE = "用法：make init dev|prod"
MODES = {"dev": "development", "prod": "production"}

# 自動產生的祕密: 變數名稱 → 產生方式。
GENERATED = {
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(24),
    "JWT_SECRET_KEY": lambda: secrets.token_hex(32),
    # Next 要求 base64 編碼的 32 bytes。
    "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY": lambda: (
        __import__("base64").b64encode(secrets.token_bytes(32)).decode()
    ),
}
MIN_UV_VERSION = (0, 13)
PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def default_project_name() -> str:
    name = re.sub(r"[^a-z0-9_-]+", "-", REPO_ROOT.name.lower()).strip("-_")
    return name or "my-app"


def ask(question: str, default: str) -> str:
    if not sys.stdin.isatty():
        return default
    answer = input(f"{question} [{default}] ").strip()
    return answer or default


def require_docker() -> None:
    if shutil.which("docker") is None:
        fail("缺少 docker")
    for command, message in (
        (["docker", "compose", "version"], "缺少 docker compose（Compose v2 以上的外掛）"),
        (["docker", "info"], "無法連上 docker daemon：請先啟動 Docker，或確認帳號在 docker 群組"),
    ):
        if subprocess.run(command, capture_output=True, check=False).returncode != 0:
            fail(message)


def project_in_use(name: str) -> list[str]:
    """容器與 volume 都以專案名稱為前綴, 撞名時新專案會接手舊專案的資料庫。"""
    found: list[str] = []
    label = f"label=com.docker.compose.project={name}"
    for kind, command in (
        ("Container", ["docker", "ps", "-a", "--filter", label, "--format", "{{.Names}}"]),
        ("Volume", ["docker", "volume", "ls", "--filter", label, "--format", "{{.Name}}"]),
    ):
        output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
        found += [f"  {kind:<10} {item}" for item in output.split()]
    return found


def write_env(mode: str) -> None:
    """照 .env.example 的順序與註解產生 .env; 既有的值原樣保留。"""
    existing = parse_env_file(ENV_FILE) if ENV_FILE.exists() else {}
    fresh = not ENV_FILE.exists()
    if existing.get("MODE") and existing["MODE"] != mode:
        fail(f".env 的 MODE 是 {existing['MODE']}，與這次的 {mode} 不同；要換環境請先移走 .env")

    values = dict(existing)
    values["MODE"] = mode
    if fresh:
        name = ask("專案名稱（容器與 volume 的前綴）", default_project_name())
        if not PROJECT_NAME_PATTERN.match(name):
            fail("專案名稱只能用小寫英數與 - _，而且以英數開頭")
        used = project_in_use(name)
        if used:
            fail(f"專案名稱「{name}」已有 docker 資源在使用，請換一個名稱：\n" + "\n".join(used))
        values["COMPOSE_PROJECT_NAME"] = name
        values["SYSTEM_NAME"] = ask("系統名稱（顯示在畫面上）", name)
        values["SYSTEM_PORT"] = ask("對外的 port", "3000")
        # journald 讓 log 在重建容器後仍查得到, 只有 Linux 主機有。
        journald = mode == "production" and shutil.which("journalctl") is not None
        values["LOG_DRIVER"] = "journald" if journald else "json-file"
    for key, generate in GENERATED.items():
        if not values.get(key):
            values[key] = generate()

    lines = []
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#"):
            line = f"{key}={values.get(key, line.split('=', 1)[1])}"
        lines.append(line)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)
    print(f"{'已建立' if fresh else '已更新'} .env（MODE={mode}）")


def install_dev_dependencies() -> None:
    for tool, hint in (("uv", "https://docs.astral.sh/uv/"), ("npm", "安裝 Node（版本見 .nvmrc）")):
        if shutil.which(tool) is None:
            fail(f"缺少 {tool}：{hint}")
    # 舊版的 uv 不認得專案用的 Python 版本, 會抓到測試版而安裝失敗。
    version = subprocess.run(["uv", "--version"], capture_output=True, text=True, check=True)
    numbers = tuple(int(part) for part in re.findall(r"\d+", version.stdout)[:2])
    if numbers < MIN_UV_VERSION:
        required = ".".join(str(part) for part in MIN_UV_VERSION)
        fail(f"uv 版本太舊（{version.stdout.strip()}），需要 {required} 以上：請先升級 uv")
    steps = (
        ("後端相依", ["uv", "sync", "--frozen"], "apps/api"),
        ("前端相依", ["npm", "ci", "--no-audit", "--no-fund"], "apps/web"),
        ("E2E 相依", ["npm", "ci", "--no-audit", "--no-fund"], "e2e"),
    )
    for label, command, directory in steps:
        if not (REPO_ROOT / directory).is_dir():
            continue
        print(f"安裝{label}…")
        subprocess.run(command, cwd=REPO_ROOT / directory, check=True)
    if (REPO_ROOT / ".git").exists() and (REPO_ROOT / ".githooks").is_dir():
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=REPO_ROOT, check=True)


def run(_name: str, args: list[str]) -> None:
    if len(args) != 1 or args[0] not in MODES:
        fail(USAGE)
    mode = MODES[args[0]]
    require_docker()
    write_env(mode)
    if mode == "development":
        install_dev_dependencies()
    print("完成。接下來：make start")
