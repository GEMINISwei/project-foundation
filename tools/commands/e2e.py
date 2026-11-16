"""make e2e: 用瀏覽器從頭到尾走過整套系統 (nginx → web → api → PostgreSQL)。

    make e2e up                 起一套常駐的 E2E 開發環境 (獨立的容器、資料與 port)
    make e2e test <檔案…>       重設資料後只跑指定的 spec (路徑相對於 e2e/)
    make e2e grep "<名稱>"      重設資料後只跑名稱符合的測試
    make e2e down               拆掉 E2E 環境與它的資料
    make e2e check              起一套拋棄式的正式環境 image 跑全部測試, 再實際備份還原一次
                                (CI 跑的就是這個)

開發中寫測試用 up + test: 原始碼是 bind mount, 改了直接生效。check 用正式環境的建置結果,
只有它驗證得到 proxy 導向、cookie 屬性這些建置後才定案的行為。

check 跑完測試後再驗兩項執行期契約, 結果寫進 Job summary (docs/foundation/testing.md〈執行期契約〉):
資料庫裡使用者輸入的文字與測試密碼沒有出現在 log、AUDIT 與任務的 payload;
容器沒有寫入 volume 以外、重建就會消失的位置。
"""

from __future__ import annotations

import os
import re
import secrets
import socket
import subprocess
import zlib
from base64 import b64encode

from tools.commands import backup
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


PLAYWRIGHT_IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from\s*[\"']@playwright/test[\"']")
MIN_SECRET = 6
ALLOWED_WRITES = (
    "/tmp",  # noqa: S108  # 容器裡允許寫入的暫存位置, 不是在這裡建立暫存檔
    "/run",
    "/var/run",
    "/var/cache/nginx",
    "/etc/nginx/conf.d",
    "/app/.next/cache",
)


def direct_playwright_imports(specs: dict[str, str]) -> list[str]:
    found = []
    for path, text in specs.items():
        names = [
            name.strip().split(" as ")[0].strip()
            for match in PLAYWRIGHT_IMPORT.finditer(text)
            for name in match.group(1).split(",")
        ]
        if "test" in names:
            found.append(path)
    return sorted(found)


def find_leaks(values: dict[str, list[str]], sources: dict[str, str]) -> list[tuple[str, str, str]]:
    leaks = []
    for label, items in values.items():
        for item in sorted({item for item in items if len(item) >= MIN_SECRET}):
            for source, text in sources.items():
                lines = [line.strip() for line in text.splitlines() if item in line]
                leaks += [(label, source, line) for line in lines[:3]]
    return leaks


def unexpected_writes(
    diffs: dict[str, list[str]], mounts: dict[str, list[str]] | None = None
) -> list[tuple[str, str]]:
    result = []
    for container, lines in diffs.items():
        paths = sorted({line.split(" ", 1)[1] for line in lines if " " in line})
        roots = (*ALLOWED_WRITES, *(mounts or {}).get(container, ()))
        for path in paths:
            parent = any(other.startswith(path + "/") for other in paths)
            allowed = any(path == root or path.startswith(root + "/") for root in roots)
            if not parent and not allowed:
                result.append((container, path))
    return result


def contracts_summary(leaks: list[tuple[str, str, str]], writes: list[tuple[str, str]]) -> str:
    if not leaks and not writes:
        return (
            "執行期契約：使用者輸入沒有出現在 log、AUDIT 與任務裡，"
            "容器也沒有寫入 volume 以外的位置。\n"
        )
    lines = ["### 執行期契約沒有通過", ""]
    if leaks:
        lines += ["#### 使用者輸入出現在 log、AUDIT 或任務裡", ""]
        lines += ["| 欄位 | 出現在 | 那一行 |", "|---|---|---|"]
        for label, source, line in leaks:
            escaped = line.replace("|", "\\|")[:200]
            lines.append(f"| {label} | {source} | {escaped} |")
        lines.append("")
    if writes:
        lines += ["#### 寫在 volume 以外、重建容器就會消失", ""]
        lines += [
            "| 容器 | 路徑 |",
            "|---|---|",
            *(f"| {name} | {path} |" for name, path in writes),
        ]
        lines.append("")
    return "\n".join(lines)


def psql(env: dict[str, str], sql: str) -> list[str]:
    result = subprocess.run(
        ["docker", "exec", f"{env['COMPOSE_PROJECT_NAME']}-postgres",
         "psql", "-U", "app", "-d", "app", "-At", "-c", sql],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return result.stdout.splitlines()


def user_input(env: dict[str, str]) -> dict[str, list[str]]:
    columns = psql(
        env,
        "SELECT table_name || '.' || column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type IN ('text', 'character varying') "
        "AND table_name NOT IN ('audit_logs', 'jobs', 'alembic_version') "
        "AND column_name NOT LIKE '%hash%' ORDER BY 1",
    )
    values = {}
    for column in columns:
        table, name = column.split(".")
        values[column] = psql(
            env,
            f'SELECT DISTINCT "{name}" FROM "{table}" WHERE "{name}" IS NOT NULL',  # noqa: S608  # 表名與欄位名取自 information_schema, 不是外部輸入
        )
    return values


def scanned_sources(env: dict[str, str]) -> dict[str, str]:
    services = compose(
        env, "ps", "-a", "--format", "{{.Service}}", capture=True, extra_env=env
    ).stdout.split()
    sources = {
        f"{service} 的 log": compose(
            env,
            "logs",
            "--no-color",
            "--no-log-prefix",
            service,
            capture=True,
            check=False,
            extra_env=env,
        ).stdout
        for service in sorted(set(services))
    }
    sources["audit_logs"] = "\n".join(psql(env, "SELECT row_to_json(t)::text FROM audit_logs t"))
    sources["jobs"] = "\n".join(psql(env, "SELECT row_to_json(t)::text FROM jobs t"))
    return sources


def container_mounts(env: dict[str, str]) -> dict[str, list[str]]:
    names = compose(env, "ps", "-a", "--format", "{{.Name}}", capture=True, extra_env=env).stdout
    prefix = f"{env['COMPOSE_PROJECT_NAME']}-"
    template = "{{range .Mounts}}{{.Destination}} {{end}}"
    return {
        name.removeprefix(prefix): subprocess.run(
            ["docker", "inspect", "-f", template, name], capture_output=True, text=True, check=True
        ).stdout.split()
        for name in sorted(names.split())
    }


def container_writes(env: dict[str, str]) -> dict[str, list[str]]:
    names = compose(
        env, "ps", "-a", "--format", "{{.Name}}", capture=True, extra_env=env
    ).stdout.split()
    prefix = f"{env['COMPOSE_PROJECT_NAME']}-"
    return {
        name.removeprefix(prefix): subprocess.run(
            ["docker", "diff", name], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        for name in sorted(names)
    }


def check_runtime_contracts(env: dict[str, str], before: dict[str, list[str]]) -> bool:
    values = {
        column: [value for value in items if value not in set(before.get(column, ()))]
        for column, items in user_input(env).items()
    }
    values["測試密碼"] = [env["E2E_ADMIN_PASSWORD"], "e2e-password-"]
    leaks = find_leaks(values, scanned_sources(env))
    writes = unexpected_writes(container_writes(env), container_mounts(env))
    summary = contracts_summary(leaks, writes)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary)
    return not leaks and not writes


def check_spec_imports() -> None:
    specs = {
        str(path.relative_to(E2E_DIR)): path.read_text(encoding="utf-8")
        for path in sorted((E2E_DIR / "tests").rglob("*.ts"))
        if path.name != "support.ts"
    }
    if found := direct_playwright_imports(specs):
        fail(
            "這些檔案直接從 @playwright/test 匯入 test，執行期契約的檢查不會套用："
            + "、".join(found)
            + '\n改成 import { test } from "../support"（setup 檔用 "./support"）'
        )


def playwright(env: dict[str, str], *args: str) -> int:
    if not (E2E_DIR / "node_modules").is_dir():
        fail("缺少 e2e 的套件：make init dev（或 cd e2e && npm ci）")
    check_spec_imports()
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
        seeded = user_input(env)
        reset_data(env)
        status = playwright(env, *(("--shard", shard) if shard else ()))
        if not check_runtime_contracts(env, seeded):
            status = 1
        if status == 0:
            # 整套系統只有這裡真的在跑: 順便實際備份再還原一次 (tools/commands/backup.py)。
            try:
                backup.verify_roundtrip(env)
            except (SystemExit, subprocess.CalledProcessError):
                status = 1
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
