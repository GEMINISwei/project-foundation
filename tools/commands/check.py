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
    make check exceptions    每個例外指名的測試真的執行到它底下那一行 (後端與前端;
                             指到 E2E 與工具測試的只確認存在)
    make check build         前端正式建置, 並確認 Next 有認到 proxy.ts

在主機上執行 (編輯器與 CI 看到的就是這個環境), 需要先 make init dev。
"""

from __future__ import annotations

import filecmp
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple

from tools.contract import CONTRACT, EXPORT_ENV, WEB_SCHEMA, generate
from tools.env import ENV_EXAMPLE, REPO_ROOT, deny_on_production, fail, load_env, parse_env_file

USAGE = (__doc__ or "").split("\n\n")[1]
API = REPO_ROOT / "apps/api"
WEB = REPO_ROOT / "apps/web"
COMPOSE_DIR = REPO_ROOT / "infra/compose"
POSTGRES_IMAGE = "postgres:18.7-alpine"


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


def run_api_test() -> None:
    step("api-test")
    quick = ("uv", "run", "--frozen", "pytest", "-q", "-n", "auto")
    sh(*quick, "-m", "not integration", cwd=API, env=EXPORT_ENV)
    # agent 的 hook 與 make 指令是獨立的小程式, 借用 api 的測試環境執行。
    for directory in (REPO_ROOT / ".agents/hooks", REPO_ROOT / "tools"):
        config = ("-c", str(directory / "pytest.ini"), "--rootdir", str(directory))
        sh(*quick, *config, str(directory / "tests"), cwd=API)


@contextmanager
def postgres() -> Iterator[dict[str, str]]:
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
        yield {**EXPORT_ENV, "POSTGRES_URL": f"postgresql+asyncpg://app:app@127.0.0.1:{port}/app"}
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def run_integration(files: list[str]) -> None:
    step("integration")
    with postgres() as env:
        if files:
            sh("uv", "run", "--frozen", "pytest", "-q", *files, cwd=API, env=env)
            return
        sh("uv", "run", "--frozen", "pytest", "-q", "--cov", "--cov-report=term", cwd=API, env=env)
        # 測試跑完資料庫已經在最新的結構上: model 與 migration 有出入就會在這裡失敗。
        sh("uv", "run", "--frozen", "python", "-m", "app.cli", "check-migrations", cwd=API, env=env)


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


class Target(NamedTuple):
    path: str
    comment_line: int
    start_line: int
    test: str
    kind: str


def comment_rules() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_pr_changes", REPO_ROOT / ".github/scripts/check-pr-changes.py"
    )
    if spec is None or spec.loader is None:
        fail("讀不到 .github/scripts/check-pr-changes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def defined_tests(text: str) -> set[str]:
    rules = comment_rules()
    names = set(rules.PY_TEST_NAME.findall(text))
    return names | {name for _, name in rules.JS_TEST_NAME.findall(text)}


def classify(path: str, test: str, test_files: dict[str, str]) -> tuple[str, list[str]]:
    defining = sorted(file for file, text in test_files.items() if test in defined_tests(text))
    if not defining:
        return "missing", []
    for app in ("api", "web"):
        files = [file for file in defining if file.startswith(f"apps/{app}/tests/")]
        if path.startswith(f"apps/{app}/") and files:
            return app, files
    return "exists", defining


def judge(target: Target, ran: dict[int, set[str]]) -> str | None:
    line = next((number for number in sorted(ran) if number >= target.start_line), None)
    if line is None:
        return f"例外底下找不到會執行的程式（從第 {target.start_line} 行起）"
    if target.test not in ran[line]:
        return f"測試「{target.test}」沒有執行到第 {line} 行"
    return None


def exceptions_summary(
    problems: list[tuple[Target, str]], covered: int, existence_only: int
) -> str:
    if not problems:
        return f"例外 {covered} 個都有測試執行到，另有 {existence_only} 個只確認測試存在。\n"
    rows = [
        f"| {target.path}:{target.comment_line} | {target.test} | {problem} |"
        for target, problem in problems
    ]
    header = ["### 例外的測試沒有執行到", "", "| 位置 | 測試 | 原因 |", "|---|---|---|"]
    return "\n".join([*header, *rows, ""])


def tracked_files() -> list[str]:
    listing = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return listing.stdout.splitlines()


def collect_targets() -> list[tuple[Target, list[str]]]:
    rules = comment_rules()
    test_lock = rules.hook_module("test_lock")
    files = tracked_files()
    test_files = {
        path: (REPO_ROOT / path).read_text(encoding="utf-8")
        for path in files
        if test_lock.is_test_file(path) and path.endswith(rules.CODE_SUFFIXES)
    }
    targets = []
    for path in files:
        if not rules.in_comment_scope(path):
            continue
        source = (REPO_ROOT / path).read_text(encoding="utf-8")
        for comment_line, start_line, test in rules.exception_targets(path, source):
            kind, tests = classify(path, test, test_files)
            targets.append((Target(path, comment_line, start_line, test, kind), tests))
    return targets


def node_ids(test_file: str, name: str) -> list[str]:
    lines = (REPO_ROOT / test_file).read_text(encoding="utf-8").splitlines()
    relative = test_file.removeprefix("apps/api/")
    result = []
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*)(?:async\s+)?def {re.escape(name)}\(", line)
        if not match:
            continue
        indent = len(match.group(1))
        owner = next(
            (
                found.group(2)
                for above in reversed(lines[:index])
                if (found := re.match(r"^(\s*)class (\w+)", above)) and len(found.group(1)) < indent
            ),
            None,
        )
        result.append(f"{relative}::{owner}::{name}" if indent and owner else f"{relative}::{name}")
    return result


def context_test(context: str) -> str | None:
    match = re.search(r"::([^:\[|]+)(?:\[.*\])?\|run$", context)
    return match.group(1) if match else None


def api_coverage(targets: list[tuple[Target, list[str]]]) -> dict[str, dict[int, set[str]]]:
    ids = sorted(
        {
            node
            for target, tests in targets
            for file in tests
            for node in node_ids(file, target.test)
        }
    )
    with tempfile.TemporaryDirectory() as directory, postgres() as env:
        report = Path(directory) / "coverage.json"
        data_file = {
            **env,
            "COVERAGE_FILE": str(Path(directory) / ".coverage"),
            "COVERAGE_CORE": "ctrace",
        }
        sh(
            "uv",
            "run",
            "--frozen",
            "pytest",
            "-q",
            "--cov",
            "--cov-context=test",
            "--cov-report=",
            "--cov-fail-under=0",
            *ids,
            cwd=API,
            env=data_file,
        )
        subprocess.run(
            ["uv", "run", "--frozen", "coverage", "json", "--show-contexts", "-o", str(report)],
            cwd=API,
            env={**os.environ, **data_file},
            capture_output=True,
            check=False,
        )
        if not report.exists():
            fail("產生不了後端的覆蓋率報告")
        files = json.loads(report.read_text(encoding="utf-8"))["files"]
    result: dict[str, dict[int, set[str]]] = {}
    for name, entry in files.items():
        executable = entry["executed_lines"] + entry["missing_lines"]
        lines: dict[int, set[str]] = {line: set() for line in executable}
        for line, contexts in entry.get("contexts", {}).items():
            lines.setdefault(int(line), set()).update(
                test for test in map(context_test, contexts) if test
            )
        result[f"apps/api/{name}"] = lines
    return result


def web_coverage(target: Target, tests: list[str]) -> dict[int, set[str]]:
    source = target.path.removeprefix("apps/web/")
    with tempfile.TemporaryDirectory() as directory:
        sh(
            "npx",
            "vitest",
            "run",
            *(file.removeprefix("apps/web/") for file in tests),
            "-t",
            re.escape(target.test),
            "--coverage.enabled=true",
            f"--coverage.include={source}",
            "--coverage.reporter=json",
            f"--coverage.reportsDirectory={directory}",
            "--coverage.thresholds.lines=0",
            "--coverage.thresholds.branches=0",
            cwd=WEB,
        )
        report = json.loads((Path(directory) / "coverage-final.json").read_text(encoding="utf-8"))
    entry = next((value for key, value in report.items() if key.endswith("/" + source)), None)
    lines: dict[int, set[str]] = {}
    for statement, location in (entry or {}).get("statementMap", {}).items():
        ran = lines.setdefault(location["start"]["line"], set())
        if entry and entry["s"][statement] > 0:
            ran.add(target.test)
    return lines


def run_exceptions() -> None:
    step("exceptions")
    targets = collect_targets()
    problems = [
        (target, f"測試「{target.test}」不在測試檔裡")
        for target, _ in targets
        if target.kind == "missing"
    ]
    api = [(target, tests) for target, tests in targets if target.kind == "api"]
    coverage = api_coverage(api) if api else {}
    for target, _ in api:
        problem = judge(target, coverage.get(target.path, {}))
        problems += [(target, problem)] if problem else []
    for target, tests in targets:
        if target.kind == "web":
            problem = judge(target, web_coverage(target, tests))
            problems += [(target, problem)] if problem else []
    covered = sum(1 for target, _ in targets if target.kind in ("api", "web"))
    existence_only = sum(1 for target, _ in targets if target.kind == "exists")
    summary = exceptions_summary(problems, covered - len(problems), existence_only)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary)
    if problems:
        fail("有例外的測試沒有執行到它底下那一行")


CHECKS = {
    "lint": run_lint,
    "types": run_types,
    "contract": run_contract,
    "migrations": run_migrations,
    "api-test": run_api_test,
    "web-test": run_web_test,
    "build": run_build,
    "exceptions": run_exceptions,
}


def run(_name: str, args: list[str]) -> None:
    deny_on_production(load_env(required=False), "make check")
    if args and args[0] == "integration":
        run_integration(args[1:])
    elif len(args) == 1 and args[0] in CHECKS:
        CHECKS[args[0]]()
    else:
        # 不帶參數不會「全部跑一次」: 完整的檢查在 CI, 照舊習慣執行的人才不會以為都過了。
        fail(USAGE)
