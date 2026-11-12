"""make check: 檢查與測試。完整的檢查在 CI 跑 (每個 job 跑其中一項), 本機只在需要時跑單項。

    make check lint          ruff (含排版)、import-linter、eslint、dependency-cruiser、knip、
                             compose 檔、nginx 設定、文件的連結
    make check types         mypy、tsc
    make check contract      契約與前端型別跟程式一致 (只讀, 不改檔)
    make check migrations    已發版的 migration 沒有被修改或刪除
    make check api-test      後端測試 (不含需要資料庫的)、agent hook 與 make 指令的測試
    make check integration [測試檔…]
                             起一個拋棄式的 PostgreSQL 跑全部後端測試與覆蓋率門檻,
                             再確認 model 與 migration 一致; 給了測試檔就只跑那幾個
    make check web-test      前端測試 (含覆蓋率門檻)
    make check build         前端正式建置, 並確認 Next 有認到 proxy.ts

在主機上執行 (編輯器與 CI 看到的就是這個環境), 需要先 make init dev。
"""

from __future__ import annotations

import filecmp
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from tools.contract import CONTRACT, EXPORT_ENV, WEB_SCHEMA, generate
from tools.env import ENV_EXAMPLE, REPO_ROOT, deny_on_production, fail, load_env, parse_env_file

USAGE = (__doc__ or "").split("\n\n")[1]
API = REPO_ROOT / "apps/api"
WEB = REPO_ROOT / "apps/web"
COMPOSE_DIR = REPO_ROOT / "infra/compose"
POSTGRES_IMAGE = "postgres:18.6-alpine"


def sh(*command: str, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env={**os.environ, **(env or {})}, check=True)


def step(title: str) -> None:
    print(f"\n── {title} " + "─" * max(4, 60 - len(title)))


# ── 各項檢查 ─────────────────────────────────────────────────────────────────


def lint_compose() -> None:
    """用 .env.example 展開每一種組合的 compose 檔: 抓語法錯誤, 也抓「compose 用了 .env.example
    沒有的必填變數」。`env -i` 隔開本機已經載入的變數, 不然本機有值就把範本的缺漏蓋過去了。"""
    values = {key: value or "placeholder" for key, value in parse_env_file(ENV_EXAMPLE).items()}
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as handle:
        handle.write("".join(f"{key}={value}\n" for key, value in values.items()))
    try:
        for mode, overlay in (("development", "dev"), ("production", "prod")):
            for driver in ("json-file", "journald"):
                files = ["compose.yml", f"compose.{overlay}.yml", f"compose.log-{driver}.yml"]
                command = ["docker", "compose", "--project-directory", str(COMPOSE_DIR)]
                command += ["--env-file", handle.name]
                for name in files:
                    command += ["-f", str(COMPOSE_DIR / name)]
                environment = {
                    "PATH": os.environ["PATH"],
                    "HOME": os.environ.get("HOME", ""),
                    "MODE": mode,
                    "NGINX_CONFIG_HASH": "lint",
                }
                subprocess.run([*command, "config", "--quiet"], env=environment, check=True)
    finally:
        os.unlink(handle.name)


def lint_infra() -> None:
    """兩件安全相關、而且寫錯了不會有任何症狀的事。"""
    problems = []
    # 容器的 nginx 信任上一層送來的用戶端 IP, 前提是外部連不到它: 正式環境只能綁 loopback。
    for name in ("compose.yml", "compose.prod.yml"):
        text = (COMPOSE_DIR / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            port = line.strip().lstrip("- ").strip("\"'")
            if port.endswith(":80") and not port.startswith("127.0.0.1:"):
                problems.append(f"{name}: nginx 的 port 必須綁 127.0.0.1（目前是 {port}）")
    # 每個轉送的 location 都要覆寫用戶端送來的標頭 (X-Real-IP 是限流的 key)。
    nginx = REPO_ROOT / "infra/nginx"
    for template in sorted(nginx.glob("*.template")):
        for block in re.findall(r"location[^{]*\{[^}]*\}", template.read_text(encoding="utf-8")):
            forwards = "proxy_pass" in block
            # WebSocket 升級的 location (開發環境的熱更新) 自己設標頭, 不帶用戶端資訊。
            if forwards and "Upgrade" not in block and "snippets/proxy-headers.conf" not in block:
                where = block.split("{")[0].strip()
                problems.append(
                    f"{template.name}: {where} 沒有 include snippets/proxy-headers.conf"
                )
    if problems:
        fail("\n".join(problems))


LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)


def anchors(path: Path) -> set[str]:
    """這份 Markdown 的標題在 GitHub 上的錨點。"""
    result = set()
    for title in HEADING.findall(path.read_text(encoding="utf-8")):
        text = re.sub(r"[`*]", "", title).strip().lower()
        result.add(re.sub(r"[^\w\- ]", "", text).replace(" ", "-"))
    return result


def lint_docs() -> None:
    """文件裡指向 repo 內的連結都要存在, 連到標題的錨點也要對得上。"""
    files = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md", REPO_ROOT / "CHANGELOG.md"]
    files += sorted((REPO_ROOT / "docs").rglob("*.md"))
    files += sorted((REPO_ROOT / ".agents/skills").rglob("*.md"))
    files += sorted((REPO_ROOT / ".github").glob("*.md"))
    broken = []
    for source in files:
        text = re.sub(r"```.*?```", "", source.read_text(encoding="utf-8"), flags=re.S)
        for link in LINK.findall(text):
            if re.match(r"^[a-z]+:", link):
                continue
            target, _, anchor = link.partition("#")
            path = (source.parent / target).resolve() if target else source
            where = f"{source.relative_to(REPO_ROOT)}: {link}"
            if not path.exists():
                broken.append(f"{where}（檔案不存在）")
            elif anchor and path.suffix == ".md" and anchor not in anchors(path):
                broken.append(f"{where}（找不到這個標題）")
    if broken:
        fail("文件的連結失效：\n" + "\n".join(broken))


def run_lint() -> None:
    step("lint")
    # tools/、agent 的 hook 與 skill 的腳本不在 api 的 import root 裡, 但同樣是 Python,
    # 套用同一份 ruff 設定。
    sources = (".", "../../tools", "../../.agents/hooks", "../../.agents/skills")
    sh("uv", "run", "--frozen", "ruff", "check", *sources, cwd=API)
    sh("uv", "run", "--frozen", "ruff", "format", "--check", *sources, cwd=API)
    sh("uv", "run", "--frozen", "lint-imports", "--no-logo", cwd=API)
    sh("npm", "run", "--silent", "lint", cwd=WEB)
    lint_compose()
    lint_infra()
    lint_docs()


def run_types() -> None:
    step("types")
    sh("uv", "run", "--frozen", "mypy", cwd=API)
    sh("npm", "run", "--silent", "typecheck", cwd=WEB)


def run_contract() -> None:
    step("contract")
    with tempfile.TemporaryDirectory() as directory:
        contract, schema = Path(directory) / "openapi.json", Path(directory) / "schema.d.ts"
        generate(contract, schema)
        stale = [
            str(current.relative_to(REPO_ROOT))
            for fresh, current in ((contract, CONTRACT), (schema, WEB_SCHEMA))
            if not current.exists() or not filecmp.cmp(fresh, current, shallow=False)
        ]
    if stale:
        fail(f"契約與程式不一致：{'、'.join(stale)}（執行 make gen-types 後一起 commit）")
    print("契約與前端型別是最新的")


def latest_release_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def run_migrations() -> None:
    """發版之後 migration 已經跑在主機上: 只能往前加, 不能修改或刪除既有的。"""
    step("migrations")
    tag = latest_release_tag()
    if tag is None:
        print("還沒有發版的 tag，略過")
        return
    diff = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", tag, "--", "apps/api/migrations/versions"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    touched = [line for line in diff.stdout.splitlines() if line and not line.startswith("A")]
    if touched:
        fail(f"{tag} 之前的 migration 不可修改或刪除，要改結構請新增一支：\n" + "\n".join(touched))
    print(f"{tag} 之前的 migration 沒有被動到")


def check_migration_direction(versions: str, db_revision: str) -> None:
    """部署前: 主機資料庫的版本必須在要部署的這一版裡。migration 只往前, 所以資料庫比程式新
    (兩版之間多了 migration) 就不能回滾到這一版。"""
    if not db_revision:
        print("資料庫還沒有跑過 migration，放行")
        return
    known = set()
    for path in Path(versions).glob("*.py"):
        known.update(re.findall(r"^revision[^=]*=\s*['\"]([^'\"]+)['\"]", path.read_text(), re.M))
    if db_revision in known:
        print(f"資料庫的版本 {db_revision} 在這一版的 migration 裡，放行")
        return
    fail(
        f"資料庫的版本 {db_revision} 比要部署的這一版新（或兩邊分岔），不能部署。可以：\n"
        "  - 往前修：修好之後發一個新版本\n"
        "  - 還原部署前的備份：在主機上 make backup restore db（會失去備份之後的資料）"
    )


def run_api_test() -> None:
    step("api-test")
    quick = ("uv", "run", "--frozen", "pytest", "-q", "-n", "auto")
    sh(*quick, "-m", "not integration", cwd=API, env=EXPORT_ENV)
    # agent 的 hook 與 make 指令是獨立的小程式, 借用 api 的測試環境執行。
    for directory in (REPO_ROOT / ".agents/hooks", REPO_ROOT / "tools"):
        config = ("-c", str(directory / "pytest.ini"), "--rootdir", str(directory))
        sh(*quick, *config, str(directory / "tests"), cwd=API)


def run_integration(files: list[str]) -> None:
    step("integration")
    name = f"check-postgres-{os.getpid()}"
    sh("docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_USER=app",
       "-e", "POSTGRES_PASSWORD=app", "-e", "POSTGRES_DB=app",
       "-e", "POSTGRES_INITDB_ARGS=--encoding=UTF8 --locale=C",
       "-p", "127.0.0.1::5432", POSTGRES_IMAGE)  # fmt: skip
    try:
        port = (
            subprocess.run(
                ["docker", "port", name, "5432/tcp"], capture_output=True, text=True, check=True
            )
            .stdout.strip()
            .rsplit(":", 1)[1]
        )
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "app"],
                capture_output=True, check=False,
            )  # fmt: skip
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            fail("拋棄式的 PostgreSQL 沒有在一分鐘內就緒")
        env = {**EXPORT_ENV, "POSTGRES_URL": f"postgresql+asyncpg://app:app@127.0.0.1:{port}/app"}
        if files:
            sh("uv", "run", "--frozen", "pytest", "-q", *files, cwd=API, env=env)
            return
        sh("uv", "run", "--frozen", "pytest", "-q", "--cov", "--cov-report=term", cwd=API, env=env)
        # 測試跑完資料庫已經在最新的結構上: model 與 migration 有出入就會在這裡失敗。
        sh("uv", "run", "--frozen", "python", "-m", "app.cli", "check-migrations", cwd=API, env=env)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def run_web_test() -> None:
    step("web-test")
    sh("npm", "run", "--silent", "test:coverage", cwd=WEB)


def run_build() -> None:
    step("build")
    result = subprocess.run(
        ["npm", "run", "--silent", "build"],
        cwd=WEB,
        capture_output=True,
        text=True,
        check=False,
        # build 期只需要 Server Action id 的 salt, 用公開的常數 (與 Dockerfile 相同)。
        env={
            **os.environ,
            "NEXT_SERVER_ACTIONS_ENCRYPTION_KEY": "cHVibGljLWFjdGlvbi1pZC1zYWx0LW5vdC1zZWNyZXQ=",
        },
    )
    print(result.stdout + result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    # proxy.ts 放錯位置 Next 照樣建置成功, 路由保護卻整層消失。
    if "Proxy (Middleware)" not in result.stdout:
        fail("建置結果裡沒有 Proxy (Middleware)：確認 apps/web/proxy.ts 在原位")


CHECKS = {
    "lint": run_lint,
    "types": run_types,
    "contract": run_contract,
    "migrations": run_migrations,
    "api-test": run_api_test,
    "web-test": run_web_test,
    "build": run_build,
}


def run(_name: str, args: list[str]) -> None:
    deny_on_production(load_env(required=False), "make check")
    if len(args) in (2, 3) and args[0] == "migration-direction":
        # 部署流程在 CI 上呼叫, 不是給人用的, 所以不列在用法裡。
        check_migration_direction(args[1], args[2] if len(args) == 3 else "")
    elif args and args[0] == "integration":
        run_integration(args[1:])
    elif len(args) == 1 and args[0] in CHECKS:
        CHECKS[args[0]]()
    else:
        # 不帶參數不會「全部跑一次」: 完整的檢查在 CI, 照舊習慣執行的人才不會以為都過了。
        fail(USAGE)
