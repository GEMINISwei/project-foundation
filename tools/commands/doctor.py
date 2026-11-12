"""make doctor: 檢查這台機器與正在執行的服務, 一次列出所有問題。

部署到新主機、升級 Docker 之後, 或「好像哪裡怪怪的」時先跑這個。只讀不改。
"""

from __future__ import annotations

import re
import subprocess
import urllib.error
import urllib.request

from tools.commands.logs import journal_problem
from tools.compose import SERVICES, app_cli, compose, container, container_running, log_driver
from tools.env import ENV_EXAMPLE, app_version, fail, load_env, parse_env_file

# compose 檔用到的功能需要的最低版本 (healthcheck 的 start_interval、`!override`)。
MIN_DOCKER = (25, 0)
MIN_COMPOSE = (2, 24)

results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def version_of(command: list[str]) -> tuple[tuple[int, ...], str]:
    output = subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()
    numbers = tuple(int(part) for part in re.findall(r"\d+", output)[:2])
    return numbers, output


def check_docker() -> None:
    for name, command, minimum in (
        ("Docker", ["docker", "version", "--format", "{{.Server.Version}}"], MIN_DOCKER),
        ("Docker Compose", ["docker", "compose", "version", "--short"], MIN_COMPOSE),
    ):
        numbers, output = version_of(command)
        required = ".".join(str(part) for part in minimum)
        if not numbers:
            record("錯誤", name, "無法取得版本，確認 Docker 已啟動")
        elif numbers < minimum:
            record("錯誤", name, f"{output}，需要 {required} 以上")
        else:
            record("正常", name, output)


def check_env(env: dict[str, str]) -> None:
    missing = [key for key in parse_env_file(ENV_EXAMPLE) if key not in env]
    if missing:
        record("警告", ".env", f"缺少 {'、'.join(missing)}（執行 make init dev|prod 補上）")
    else:
        record("正常", ".env", f"MODE={env.get('MODE')}，LOG_DRIVER={log_driver(env)}")
    if env.get("MODE") == "production" and log_driver(env) == "json-file":
        record(
            "警告",
            "log 保留",
            "LOG_DRIVER=json-file：重建容器（每次部署）後舊的 log 會消失；"
            "Linux 主機建議用 journald",
        )


def check_journal(env: dict[str, str]) -> None:
    """log 交給 journald 時, 這個帳號要讀得到: 讀不到的話 make logs 什麼都查不出來。"""
    if log_driver(env) != "journald":
        return
    problem = journal_problem()
    record("錯誤" if problem else "正常", "log 查詢", problem or "讀得到 journald")


def check_services(env: dict[str, str]) -> bool:
    result = compose(
        env, "ps", "--all", "--format", "{{.Service}}\t{{.State}}\t{{.Health}}", capture=True
    )
    states = {
        line.split("\t")[0]: line.split("\t")[1:] for line in result.stdout.splitlines() if line
    }
    healthy = True
    for service in SERVICES:
        state, health = (states.get(service) or ["不存在", ""])[:2]
        if service == "migrate":
            ok = state == "exited"
            detail = "已完成" if ok else f"{state}（migration 沒有成功結束，見 make logs migrate）"
        else:
            ok = state == "running" and health in ("", "healthy")
            detail = "執行中" if ok else f"{state} {health}".strip()
        record("正常" if ok else "錯誤", f"服務 {service}", detail)
        healthy = healthy and ok
    return healthy


def check_runtime(env: dict[str, str]) -> None:
    url = f"http://127.0.0.1:{env.get('SYSTEM_PORT', '3000')}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            record("正常", "對外入口", f"{url} → {response.status}")
    except (urllib.error.URLError, OSError) as error:
        record("錯誤", "對外入口", f"{url} 連不上：{error}")

    query = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"'
    )
    revision = subprocess.run(
        ["docker", "exec", container(env, "postgres"), "sh", "-c", query],
        capture_output=True,
        text=True,
        check=False,
    )
    record(
        "正常" if revision.returncode == 0 else "錯誤",
        "資料庫結構",
        revision.stdout.strip() or "讀不到版本",
    )

    failed = app_cli(env, "jobs", "list", "failed", capture=True, check=False)
    count = max(len([line for line in failed.stdout.splitlines() if "failed" in line]), 0)
    if count:
        record("警告", "背景任務", f"有 {count} 個失敗的任務（make jobs list failed）")
    else:
        record("正常", "背景任務", "沒有失敗的任務")


def run(_name: str, args: list[str]) -> None:
    if args:
        fail("用法：make doctor")
    env = load_env()
    record("正常", "版本", f"v{app_version()}")
    check_docker()
    check_env(env)
    check_journal(env)
    if any(container_running(env, service) for service in SERVICES):
        if check_services(env):
            check_runtime(env)
    else:
        record("警告", "服務", "沒有在執行（make start）")

    width = max(len(name) for _, name, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name:<{width}}  {detail}")
    if any(status == "錯誤" for status, _, _ in results):
        raise SystemExit(1)
