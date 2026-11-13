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

# api 的記憶體上限隨行程數調整: 每個行程各載入一份完整的應用程式, 用量與行程數成正比。
# 第一份含 Python 執行環境與餘裕; 數字依實測 (見 docs/foundation/operations.md#擴充)。
API_MEMORY_BASE_MB = 512
API_MEMORY_PER_EXTRA_PROCESS_MB = 256
# 每個行程 (api 的每個行程、每一份 worker) 的連線池上限:
# apps/api 的 db_pool_size + db_max_overflow 的預設值。
CONNECTIONS_PER_PROCESS = 15
# PostgreSQL 的 max_connections 預設 100, 留 10 條給 migrate、psql 與維運指令。
MAX_APP_CONNECTIONS = 90


def count_setting(env: dict[str, str], name: str) -> int:
    """`.env` 裡的行程數或份數; 沒設就是 1。"""
    value = env.get(name) or "1"
    if not value.isdigit() or int(value) < 1:
        fail(f".env 的 {name} 必須是正整數（目前是「{value}」）")
    return int(value)


def api_memory_limit(env: dict[str, str]) -> str:
    extra = count_setting(env, "API_PROCESSES") - 1
    return f"{API_MEMORY_BASE_MB + API_MEMORY_PER_EXTRA_PROCESS_MB * extra}M"


def check_capacity(env: dict[str, str]) -> None:
    """連線數超過 PostgreSQL 的上限時平常不會出錯, 要等流量大、連線池用滿才出現,
    所以啟動前就擋下。"""
    processes = count_setting(env, "API_PROCESSES") + count_setting(env, "WORKER_REPLICAS")
    if processes * CONNECTIONS_PER_PROCESS > MAX_APP_CONNECTIONS:
        fail(
            f".env 的 API_PROCESSES 與 WORKER_REPLICAS 加起來最多 "
            f"{MAX_APP_CONNECTIONS // CONNECTIONS_PER_PROCESS}（目前是 {processes}）："
            f"每個行程最多佔 {CONNECTIONS_PER_PROCESS} 條資料庫連線"
        )


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
    process_env = {
        **os.environ,
        "NGINX_CONFIG_HASH": nginx_config_hash(),
        "API_MEMORY_LIMIT": api_memory_limit(env),
        **(extra_env or {}),
    }
    return subprocess.run(
        [*compose_command(env), *args],
        env=process_env,
        check=check,
        text=True,
        capture_output=capture,
    )


def container(env: dict[str, str], service: str) -> str:
    """只有一個容器的服務 (worker 以外) 的容器名稱。"""
    return f"{env['COMPOSE_PROJECT_NAME']}-{service}"


def containers(env: dict[str, str], service: str) -> list[str]:
    """一個服務的所有容器。worker 可以開多份, compose 依序命名成 `<專案>-worker-<序號>`。"""
    if service == "worker":
        replicas = count_setting(env, "WORKER_REPLICAS")
        return [f"{env['COMPOSE_PROJECT_NAME']}-worker-{n}" for n in range(1, replicas + 1)]
    return [container(env, service)]


def running_containers() -> set[str]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return set(result.stdout.split())


def container_running(env: dict[str, str], service: str) -> bool:
    """服務有任何一個容器在執行。"""
    running = running_containers()
    return any(name in running for name in containers(env, service))


def container_state(name: str) -> str:
    """容器的狀態; 有 healthcheck 的在執行中時回報健康狀態 (starting / healthy / unhealthy)。"""
    template = "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}"
    result = subprocess.run(
        ["docker", "inspect", "--format", template, name],
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
    """等服務的每個容器就緒; 回傳逾時仍未就緒的容器與當下的狀態 (空的代表全部就緒)。"""
    names = [name for service in services for name in containers(env, service)]
    return wait_for_containers(names, timeout)


def wait_for_containers(
    names: Sequence[str], timeout: float = READY_TIMEOUT_SECONDS
) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while True:
        pending = {name: state for name in names if not is_ready(state := container_state(name))}
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
    running = running_containers()
    stopped = [name for service in services for name in containers(env, service) if name in running]
    if stopped:
        print(f"暫停服務：{'、'.join(stopped)}（等進行中的請求與任務做完）")
    for name in stopped:
        subprocess.run(["docker", "stop", name], check=True, capture_output=True)
    try:
        yield
    except BaseException:
        if resume_on_failure:
            resume(stopped)
        elif stopped:
            print(f"失敗：{'、'.join(stopped)} 維持停止，確認資料沒問題後執行 make start")
        raise
    resume(stopped)


def resume(stopped: Sequence[str]) -> None:
    if not stopped:
        return
    # 與停止相反的順序: 後面的服務先起來, 最後才接回流量。
    for name in reversed(stopped):
        subprocess.run(["docker", "start", name], check=True, capture_output=True)
    pending = wait_for_containers(stopped)
    if pending:
        fail(f"服務沒有恢復正常：{describe(pending)}（make logs 查看原因）")
    print("已恢復服務")


def describe(pending: dict[str, str]) -> str:
    return "、".join(f"{name}（{state}）" for name, state in pending.items())


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
