"""make e2e: 用瀏覽器從頭到尾走過整套系統 (nginx → web → api → PostgreSQL)。

    make e2e up                 起一套常駐的 E2E 開發環境 (獨立的容器、資料與 port)
    make e2e test <檔案…>       重設資料後只跑指定的 spec (路徑相對於 e2e/)
    make e2e grep "<名稱>"      重設資料後只跑名稱符合的測試
    make e2e down               拆掉 E2E 環境與它的資料
    make e2e check              起一套拋棄式的正式環境 image 跑全部測試 (CI 跑的就是這個)

開發中寫測試用 up + test: 原始碼是 bind mount, 改了直接生效。check 用正式環境的建置結果,
只有它驗證得到 proxy 導向、cookie 屬性這些建置後才定案的行為。
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import zlib
from base64 import b64encode

from tools.compose import compose, container_running
from tools.env import REPO_ROOT, deny_on_production, fail, load_env, parse_env_file

USAGE = (__doc__ or "").split("\n\n")[1]
STATE = REPO_ROOT / ".env.e2e"
E2E_DIR = REPO_ROOT / "e2e"


def free_port() -> int:
    for port in range(3901, 4000):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    fail("3901 到 3999 都有人在用，找不到空的 port")


def new_stack(base: dict[str, str], *, mode: str, suffix: str) -> dict[str, str]:
    """一套獨立的環境: 自己的專案名稱 (所以容器、volume 都分開)、port 與金鑰。"""
    # 同一個專案的每個 checkout 各一套, 名稱帶上路徑的雜湊才不會互撞。
    tag = zlib.crc32(str(REPO_ROOT).encode())
    return {
        "MODE": mode,
        "COMPOSE_PROJECT_NAME": f"{base['COMPOSE_PROJECT_NAME']}-{suffix}-{tag}",
        "SYSTEM_NAME": "E2E",
        "SYSTEM_PORT": str(free_port()),
        "TIMEZONE": "Asia/Taipei",
        "EXPIRE_HOURS": "1",
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "JWT_SECRET_KEY": secrets.token_hex(32),
        "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY": b64encode(secrets.token_bytes(32)).decode(),
        "LOG_DRIVER": "json-file",
        "E2E_ADMIN_USERNAME": "e2e-admin",
        "E2E_ADMIN_PASSWORD": secrets.token_hex(16),
    }


def write_state(values: dict[str, str]) -> None:
    STATE.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    STATE.chmod(0o600)


def stack_env() -> dict[str, str]:
    if not STATE.exists():
        fail("這個 checkout 還沒有 E2E 環境，請先 make e2e up")
    return {**parse_env_file(STATE), "COMPOSE_ENV_FILE": str(STATE)}


def run_compose(env: dict[str, str], *args: str, **kwargs: object) -> None:
    # 這套環境的變數一律來自 .env.e2e, 不能混到主機 .env 已經載入的值。
    compose(env, *args, extra_env=env, **kwargs)  # type: ignore[arg-type]


def up(env: dict[str, str], *flags: str) -> None:
    run_compose(env, "run", "--rm", "-T", *flags, "migrate")
    run_compose(env, "up", "-d", "--wait", "--remove-orphans", *flags)


def reset_data(env: dict[str, str]) -> None:
    """每次跑測試前回到只有一個超管的狀態, 測試之間才不會互相影響。"""
    api = f"{env['COMPOSE_PROJECT_NAME']}-api"
    cli = ["docker", "exec", "-i", api, "python", "-m", "app.cli"]
    answers = f"E2E 超管\n{env['E2E_ADMIN_USERNAME']}\n{env['E2E_ADMIN_PASSWORD']}\n"
    quiet = {"capture_output": True, "text": True, "check": True}
    try:
        if env["MODE"] == "development":
            subprocess.run([*cli, "reset"], **quiet)  # type: ignore[call-overload]
            subprocess.run([*cli, "migrate"], **quiet)  # type: ignore[call-overload]
        subprocess.run([*cli, "superuser"], input=answers, **quiet)  # type: ignore[call-overload]
    except subprocess.CalledProcessError as error:
        fail(f"{error.stdout}{error.stderr}\n重設 E2E 環境的資料失敗（見上方訊息）")


def playwright(env: dict[str, str], *args: str) -> int:
    if not (E2E_DIR / "node_modules").is_dir():
        fail("缺少 e2e 的套件：make init dev（或 cd e2e && npm ci）")
    subprocess.run(["npm", "run", "--silent", "typecheck"], cwd=E2E_DIR, check=True)
    subprocess.run(
        ["npx", "playwright", "install", "chromium"], cwd=E2E_DIR, check=True, capture_output=True
    )
    test_env = {
        **os.environ,
        "E2E_BASE_URL": f"http://localhost:{env['SYSTEM_PORT']}",
        "E2E_ADMIN_USERNAME": env["E2E_ADMIN_USERNAME"],
        "E2E_ADMIN_PASSWORD": env["E2E_ADMIN_PASSWORD"],
    }
    return subprocess.run(
        ["npx", "playwright", "test", *args], cwd=E2E_DIR, env=test_env, check=False
    ).returncode


def cmd_up(base: dict[str, str]) -> None:
    if not STATE.exists():
        write_state(new_stack(base, mode="development", suffix="e2e"))
    env = stack_env()
    up(env)
    print(f"E2E 環境：http://localhost:{env['SYSTEM_PORT']}（{env['COMPOSE_PROJECT_NAME']}）")
    print('  make e2e test <檔案…>｜make e2e grep "名稱" 跑測試，make e2e down 拆掉')


def cmd_test(args: list[str]) -> None:
    env = stack_env()
    if not container_running(env, "api"):
        fail(f"E2E 環境（{env['COMPOSE_PROJECT_NAME']}）沒有在執行，請先 make e2e up")
    reset_data(env)
    raise SystemExit(playwright(env, *args))


def cmd_down() -> None:
    if not STATE.exists():
        print("這個 checkout 沒有 E2E 環境")
        return
    run_compose(stack_env(), "down", "-v", "--remove-orphans")
    STATE.unlink()


def cmd_check(base: dict[str, str]) -> None:
    """拋棄式的正式環境: 建置 image、跑全部測試, 不論結果都拆掉。"""
    env = new_stack(base, mode="production", suffix="e2e-check")
    path = REPO_ROOT / ".env.e2e-check"
    path.write_text("".join(f"{key}={value}\n" for key, value in env.items()), encoding="utf-8")
    env["COMPOSE_ENV_FILE"] = str(path)
    # CI 先用有快取的方式建好 image 再交進來; 本機沒給就在這裡建置。
    prebuilt = bool(os.environ.get("API_IMAGE") and os.environ.get("WEB_IMAGE"))
    if prebuilt:
        env["IMAGE_PULL_POLICY"] = "never"
    shard = os.environ.get("E2E_SHARD")
    try:
        up(env, *(() if prebuilt else ("--build",)))
        reset_data(env)
        status = playwright(env, *(("--shard", shard) if shard else ()))
        if status != 0:
            # 失敗時把各服務的 log 留在輸出裡: 環境馬上就拆掉了。
            run_compose(env, "logs", "--no-color", "--tail", "200", check=False)
    finally:
        cleanup = () if prebuilt else ("--rmi", "local")
        run_compose(env, "down", "-v", "--remove-orphans", *cleanup, check=False)
        path.unlink(missing_ok=True)
    raise SystemExit(status)


def run(_name: str, args: list[str]) -> None:
    base = load_env(required=False)
    deny_on_production(base, "make e2e")
    base.setdefault("COMPOSE_PROJECT_NAME", REPO_ROOT.name.lower())
    if args == ["up"]:
        cmd_up(base)
    elif len(args) >= 2 and args[0] == "test":
        cmd_test(args[1:])
    elif len(args) == 2 and args[0] == "grep" and args[1]:
        cmd_test(["--grep", args[1]])
    elif args == ["down"]:
        cmd_down()
    elif args == ["check"]:
        cmd_check(base)
    else:
        fail(USAGE)
