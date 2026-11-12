"""docker compose 的呼叫方式。旗標只在這裡組一次, 其他地方一律經過這個模組。"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from tools.env import REPO_ROOT, fail, require_env, require_mode

COMPOSE_DIR = REPO_ROOT / "infra/compose"
NGINX_DIR = REPO_ROOT / "infra/nginx"
LOG_DRIVERS = ("json-file", "journald")
SERVICES = ("nginx", "web", "api", "worker", "postgres", "migrate")
#: 會改到資料的服務, 依停止的順序: 先擋住外面進來的請求, 最後才是自己會動的 worker。
WRITERS = ("nginx", "web", "api", "worker")
#: 長駐的服務; 啟動之後全部就緒才算成功。
LONG_RUNNING = ("postgres", "api", "worker", "web", "nginx")
READY_TIMEOUT_SECONDS = 180


def nginx_config_hash() -> str:
    """nginx 設定是 bind mount, 內容變了 compose 看不出來; 雜湊放進 label 才會重建容器。"""
    digest = hashlib.sha256()
    for path in sorted(NGINX_DIR.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(NGINX_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def log_driver(env: dict[str, str]) -> str:
    driver = env.get("LOG_DRIVER") or "json-file"
    if driver not in LOG_DRIVERS:
        fail(f".env 的 LOG_DRIVER 必須是 {' 或 '.join(LOG_DRIVERS)}（目前是「{driver}」）")
    return driver


def compose_command(env: dict[str, str]) -> list[str]:
    """`--project-directory` 決定 compose 檔裡相對路徑的基準, `--env-file` 讀 repo 根的 .env。"""
    require_env(env, "COMPOSE_PROJECT_NAME")
    overlay = "dev" if require_mode(env) == "development" else "prod"
    files = ["compose.yml", f"compose.{overlay}.yml", f"compose.log-{log_driver(env)}.yml"]
    command = [
        "docker",
        "compose",
        "--project-directory",
        str(COMPOSE_DIR),
        "--env-file",
        env.get("COMPOSE_ENV_FILE") or str(REPO_ROOT / ".env"),
    ]
    for name in files:
        command += ["-f", str(COMPOSE_DIR / name)]
    return command


def compose(
    env: dict[str, str],
    *args: str,
    check: bool = True,
    capture: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_env = {**os.environ, "NGINX_CONFIG_HASH": nginx_config_hash(), **(extra_env or {})}
    return subprocess.run(
        [*compose_command(env), *args],
        env=process_env,
        check=check,
        text=True,
        capture_output=capture,
    )


def container(env: dict[str, str], service: str) -> str:
    return f"{env['COMPOSE_PROJECT_NAME']}-{service}"


def container_running(env: dict[str, str], service: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return container(env, service) in result.stdout.split()


def container_state(env: dict[str, str], service: str) -> str:
    """容器的狀態; 有 healthcheck 的在執行中時回報健康狀態 (starting / healthy / unhealthy)。"""
    template = "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}"
    result = subprocess.run(
        ["docker", "inspect", "--format", template, container(env, service)],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return "missing"
    status, _, health = result.stdout.strip().partition(" ")
    return health if status == "running" and health else status


def is_ready(state: str) -> bool:
    # "running" 是沒有 healthcheck 的服務 (nginx); 有 healthcheck 的要等到 healthy。
    return state in ("running", "healthy")


def wait_until_ready(
    env: dict[str, str], services: Sequence[str], timeout: float = READY_TIMEOUT_SECONDS
) -> dict[str, str]:
    """等服務就緒; 回傳逾時仍未就緒的服務與當下的狀態 (空的代表全部就緒)。"""
    deadline = time.monotonic() + timeout
    while True:
        pending = {
            service: state
            for service in services
            if not is_ready(state := container_state(env, service))
        }
        if not pending or time.monotonic() >= deadline:
            return pending
        time.sleep(1)


def entry_responds(env: dict[str, str], timeout: float = 30) -> bool:
    """從對外的入口實際打一次: nginx → web 這段路通不通, 容器各自健康看不出來。"""
    url = f"http://127.0.0.1:{env['SYSTEM_PORT']}/healthz"
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


@contextmanager
def paused(
    env: dict[str, str], services: Sequence[str], *, resume_on_failure: bool
) -> Iterator[None]:
    """停掉指定的服務再執行, 完成後照原樣開回來。本來就沒在跑的不動它。

    `docker stop` 會等容器自己結束 (compose 設定的 stop_grace_period): 進行中的請求與任務做完才停。
    `resume_on_failure=False` 給會改資料的動作用: 失敗時資料的狀態不明, 不能自動恢復服務。
    """
    stopped = [service for service in services if container_running(env, service)]
    if stopped:
        print(f"暫停服務：{'、'.join(stopped)}（等進行中的請求與任務做完）")
    for service in stopped:
        subprocess.run(["docker", "stop", container(env, service)], check=True, capture_output=True)
    try:
        yield
    except BaseException:
        if resume_on_failure:
            resume(env, stopped)
        elif stopped:
            print(f"失敗：{'、'.join(stopped)} 維持停止，確認資料沒問題後執行 make start")
        raise
    resume(env, stopped)


def resume(env: dict[str, str], stopped: Sequence[str]) -> None:
    if not stopped:
        return
    # 與停止相反的順序: 後面的服務先起來, 最後才接回流量。
    for service in reversed(stopped):
        subprocess.run(
            ["docker", "start", container(env, service)], check=True, capture_output=True
        )
    pending = wait_until_ready(env, stopped)
    if pending:
        fail(f"服務沒有恢復正常：{describe(pending)}（make logs 查看原因）")
    print("已恢復服務")


def describe(pending: dict[str, str]) -> str:
    return "、".join(f"{service}（{state}）" for service, state in pending.items())


def docker_exec(
    env: dict[str, str],
    service: str,
    command: Sequence[str],
    *,
    interactive: bool = False,
    stdin: str | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not container_running(env, service):
        fail(f"{container(env, service)} 沒有在執行，請先 make start")
    flags = ["-it"] if interactive else (["-i"] if stdin is not None else [])
    return subprocess.run(
        ["docker", "exec", *flags, container(env, service), *command],
        check=check,
        text=True,
        input=stdin,
        capture_output=capture,
    )


def app_cli(env: dict[str, str], *args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    """api 容器裡的管理指令 (apps/api/app/cli.py)。"""
    return docker_exec(env, "api", ["python", "-m", "app.cli", *args], **kwargs)  # type: ignore[arg-type]


def postgres_tool(
    env: dict[str, str], tool: str, *args: str, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """在 postgres 容器裡跑 PostgreSQL 工具; 帳號與資料庫名稱由容器自己的環境變數補上。"""
    script = 'exec "$@" -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
    return docker_exec(env, "postgres", ["sh", "-c", script, "sh", tool, *args], **kwargs)  # type: ignore[arg-type]
