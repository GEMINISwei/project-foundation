"""make doctor: 檢查這台機器與正在執行的服務, 一次列出所有問題。

部署到新主機、升級 Docker 之後, 或「好像哪裡怪怪的」時先跑這個。只讀不改。

輸出分三區: 架構環境、容器服務、Nginx 相關 (主機的 reverse proxy, 有裝才顯示)。
主機那層在 repo 之外, 少了設定也不會報錯 (docs/foundation/operations.md〈主機的 reverse proxy〉),
所以這裡讀它的設定檔把缺的列出來; 只提供診斷, 不影響部署。
"""

from __future__ import annotations

import re
import shutil
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

from tools.commands.logs import journal_problem
from tools.compose import SERVICES, compose, container, container_running, log_driver
from tools.env import ENV_EXAMPLE, app_version, fail, load_env, parse_env_file

# compose 檔用到的功能需要的最低版本 (healthcheck 的 start_interval、`!override`)。
MIN_DOCKER = (25, 0)
MIN_COMPOSE = (2, 24)

HOST_NGINX_DIR = Path("/etc/nginx")
# 與容器 nginx、Next 的上限相同 (infra/nginx/default.conf.template)。
REQUIRED_UPLOAD_BYTES = 16 * 1024 * 1024
# certbot 在剩 30 天時就會更新: 剩得比這個少代表自動更新沒有在運作。
CERT_WARNING_DAYS = 14

SECTIONS = ("架構環境", "容器服務", "Nginx 相關")
# 名稱一律用英文: 中英混排的欄位在不同字型下對不齊。
ENVIRONMENT_NAMES = ("System", "Docker", "Compose", "Log", "Nginx", "Database", ".env")
HOST_NGINX_NAMES = ("Host", "Cert", "Config", "Header", "Upload")

Result = tuple[str, str, str]
results: list[Result] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def render(entries: list[Result]) -> list[str]:
    """依名稱分到三區; 內容從同一欄開始, 沒有項目的區不顯示。"""
    groups: dict[str, list[Result]] = {title: [] for title in SECTIONS}
    for entry in entries:
        if entry[1] in ENVIRONMENT_NAMES:
            groups[SECTIONS[0]].append(entry)
        elif entry[1] in HOST_NGINX_NAMES:
            groups[SECTIONS[2]].append(entry)
        else:
            groups[SECTIONS[1]].append(entry)
    # 資料庫結構要等服務檢查完才讀得到, 顯示時照固定的順序排回第一區。
    groups[SECTIONS[0]].sort(key=lambda entry: ENVIRONMENT_NAMES.index(entry[1]))
    width = max((len(name) for _, name, _ in entries), default=0)
    lines: list[str] = []
    for title in SECTIONS:
        if not groups[title]:
            continue
        if lines:
            lines.append("")
        lines.append(title)
        lines += [f"[{status}] {name:<{width}}  {detail}" for status, name, detail in groups[title]]
    return lines


# ── 架構環境 ─────────────────────────────────────────────────────────────────


def version_of(command: list[str]) -> tuple[tuple[int, ...], str]:
    output = subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()
    numbers = tuple(int(part) for part in re.findall(r"\d+", output)[:2])
    return numbers, output


def check_docker() -> None:
    for name, command, minimum in (
        ("Docker", ["docker", "version", "--format", "{{.Server.Version}}"], MIN_DOCKER),
        ("Compose", ["docker", "compose", "version", "--short"], MIN_COMPOSE),
    ):
        numbers, output = version_of(command)
        required = ".".join(str(part) for part in minimum)
        if not numbers:
            record("錯誤", name, "無法取得版本 (確認 Docker 已啟動)")
        elif numbers < minimum:
            record("錯誤", name, f"{output} (需要 {required} 以上)")
        else:
            record("正常", name, output)


def check_journal(env: dict[str, str]) -> None:
    """log 交給 journald 時, 這個帳號要讀得到: 讀不到的話 make logs 什麼都查不出來。"""
    driver = log_driver(env)
    if driver == "journald":
        problem = journal_problem()
        record("錯誤" if problem else "正常", "Log", f"journald ({problem})" if problem else driver)
    elif env.get("MODE") == "production":
        record(
            "警告",
            "Log",
            f"{driver} (每次部署重建容器後舊的 log 會消失，Linux 主機建議用 journald)",
        )
    else:
        record("正常", "Log", driver)


def check_env(env: dict[str, str]) -> None:
    missing = [key for key in parse_env_file(ENV_EXAMPLE) if key not in env]
    if missing:
        record("警告", ".env", f"缺少 {'、'.join(missing)} (make init dev|prod 補上)")


# ── 容器服務 ─────────────────────────────────────────────────────────────────


def worker_line(states: list[tuple[str, str]], counts: tuple[int, int] | None) -> tuple[str, str]:
    """所有 worker 併成一行: 幾支在跑, 以及全系統待處理與失敗的任務。

    佇列是共用的, 筆數分不到每一支。
    """
    running = sum(1 for state, health in states if state == "running" and health in ("", "healthy"))
    others = [
        f"{state} {health}".strip()
        for state, health in states
        if not (state == "running" and health in ("", "healthy"))
    ]
    parts = [f"{running} 支運轉中"]
    parts += [f"{others.count(label)} 支 {label}" for label in dict.fromkeys(others)]
    if counts:
        parts += [f"待處理 {counts[0]} 筆", f"失敗 {counts[1]} 筆"]
    detail = "、".join(parts)
    if others or not states:
        return "錯誤", detail
    if counts and counts[1]:
        return "警告", f"{detail} (make jobs list failed)"
    return "正常", detail


def job_counts(env: dict[str, str]) -> tuple[int, int] | None:
    """待處理與失敗的任務筆數; 讀不到 (資料庫沒在跑、還沒有資料表) 時是 None。"""
    query = (
        "SELECT count(*) FILTER (WHERE status = 'pending'), "
        "count(*) FILTER (WHERE status = 'failed') FROM jobs"
    )
    script = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -AtF, -c "$1"'
    result = subprocess.run(
        ["docker", "exec", container(env, "postgres"), "sh", "-c", script, "sh", query],
        capture_output=True,
        text=True,
        check=False,
    )
    numbers = result.stdout.strip().split(",")
    if result.returncode != 0 or len(numbers) != 2 or not all(n.isdigit() for n in numbers):
        return None
    return int(numbers[0]), int(numbers[1])


def check_services(env: dict[str, str]) -> bool:
    result = compose(
        env, "ps", "--all", "--format", "{{.Service}}\t{{.State}}\t{{.Health}}", capture=True
    )
    # worker 可以開多份: 同一個服務有多行, 每一份都要正常。
    states: dict[str, list[tuple[str, str]]] = {}
    for line in result.stdout.splitlines():
        if line:
            service, state, health = [*line.split("\t"), "", ""][:3]
            states.setdefault(service, []).append((state, health))
    healthy = True
    for service in (name for name in SERVICES if name != "worker"):
        state, health = (states.get(service) or [("不存在", "")])[0]
        if service == "migrate":
            ok = state == "exited"
            detail = "已完成" if ok else f"{state} (migration 沒有成功結束，見 make logs migrate)"
        else:
            ok = state == "running" and health in ("", "healthy")
            detail = "執行中" if ok else f"{state} {health}".strip()
        record("正常" if ok else "錯誤", service, detail)
        healthy = healthy and ok
    status, detail = worker_line(states.get("worker", []), job_counts(env))
    record(status, "worker", detail)
    return healthy and status != "錯誤"


def check_runtime(env: dict[str, str]) -> None:
    port = env.get("SYSTEM_PORT", "3000")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
            record("正常", "entry", f"127.0.0.1:{port} → {response.status}")
    except (urllib.error.URLError, OSError) as error:
        record("錯誤", "entry", f"127.0.0.1:{port} 連不上 ({error})")

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
        "Database",
        revision.stdout.strip() or "讀不到版本",
    )


# ── Nginx 相關 (主機的 reverse proxy) ────────────────────────────────────────


def _expand_includes(text: str, include: Callable[[str], str | None] | None, depth: int = 3) -> str:
    """去掉註解並把 `include` 換成檔案內容: 標頭常寫在共用的片段裡 (Ubuntu 的 proxy_params)。"""
    text = re.sub(r"#[^\n]*", "", text)
    if include is None or depth == 0:
        return text

    def replace(match: re.Match[str]) -> str:
        content = include(match.group(1).strip().strip("\"'"))
        return _expand_includes(content, include, depth - 1) if content else ""

    return re.sub(r"\binclude\s+([^;]+);", replace, text)


def _server_blocks(text: str) -> Iterator[str]:
    for match in re.finditer(r"\bserver\s*\{", text):
        depth, index = 1, match.end()
        while index < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[index], 0)
            index += 1
        yield text[match.end() : index - 1]


def _size_in_bytes(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)([kmg]?)", value.lower())
    if not match:
        return None
    return int(match.group(1)) * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[match.group(2)]


def _block_lines(name: str, block: str, port: str, http: str) -> tuple[list[Result], str]:
    """一個 server 區塊的檢查結果, 以及要查憑證的網域 (沒有 HTTPS 時是空字串)。"""
    https = bool(re.search(r"\blisten\s+[^;]*\bssl\b", block)) or "ssl_certificate" in block
    server_name = re.search(r"\bserver_name\s+([^;]+);", block)
    domain = server_name.group(1).split()[0] if server_name else ""
    present: list[str] = []
    missing: list[Result] = []

    if re.search(r"\bproxy_set_header\s+X-Real-IP\s+\$remote_addr\s*;", block):
        present.append("X-Real-IP")
    else:
        missing.append(("警告", "Header", "缺少 X-Real-IP (全站共用一份登入限流額度)"))
    if re.search(r"\bproxy_set_header\s+X-Forwarded-Proto\s+[^;]+;", block):
        present.append("X-Forwarded-Proto")
    else:
        missing.append(("警告", "Header", "缺少 X-Forwarded-Proto (cookie 不會帶 Secure)"))

    # 沒寫在這一段時看 http 層 (nginx.conf) 的設定; 都沒有就是 nginx 預設的 1m。
    sizes = re.findall(r"\bclient_max_body_size\s+([^;\s]+)\s*;", block) or re.findall(
        r"\bclient_max_body_size\s+([^;\s]+)\s*;", http
    )
    size = sizes[-1] if sizes else ""
    size_bytes = _size_in_bytes(size) if size else 1024**2
    # 0 是不限制。
    if size_bytes is not None and (size_bytes == 0 or size_bytes >= REQUIRED_UPLOAD_BYTES):
        present.append(f"上傳上限 {size}")
    else:
        problem = f"上傳上限只有 {size}" if size else "沒有設定上傳上限 (nginx 預設 1m)"
        missing.append(("警告", "Upload", f"{problem}，需要 16m：超過的上傳在主機就被擋下"))

    if https:
        if re.search(r"\badd_header\s+Strict-Transport-Security\b", block):
            present.append("HSTS")
        else:
            missing.append(("警告", "Header", "缺少 HSTS (建議：瀏覽器第一次連線可能先走 HTTP)"))

    lines: list[Result] = [("正常", "Host", f"{name} → 127.0.0.1:{port}")]
    if present:
        lines.append(("正常", "Config", "、".join(present)))
    lines += missing
    if not https:
        lines.append(
            ("警告", "Cert", f"{domain or name} 沒有 HTTPS (連線沒有加密，cookie 不帶 Secure)")
        )
    return lines, domain if https else ""


def host_nginx_lines(
    files: dict[str, str],
    port: str,
    include: Callable[[str], str | None] | None = None,
    http: str = "",
) -> tuple[list[Result], list[str]]:
    """主機 nginx 的設定檔 (檔名 → 內容) 裡轉送到這個專案 port 的區塊, 各自缺了什麼。

    用文字比對, 不是完整的解析器: 認得標準寫法, 特殊的寫法 (具名的 upstream) 會被當成找不到。
    讀的是檔案, 改了還沒 reload 時看到的是新內容。
    """
    target = re.compile(rf"\bproxy_pass\s+https?://(?:127\.0\.0\.1|localhost|\[::1\]):{port}\b")
    lines: list[Result] = []
    domains: list[str] = []
    for name in sorted(files):
        for block in _server_blocks(_expand_includes(files[name], include)):
            if target.search(block):
                block_lines, domain = _block_lines(name, block, port, _expand_includes(http, None))
                lines += block_lines
                if domain:
                    domains.append(domain)
    if not lines:
        detail = f"找不到轉送到 127.0.0.1:{port} 的設定 (還沒設定網域，或寫法認不出來)"
        return [("警告", "Host", detail)], []
    return lines, domains


def certificate_line(
    domain: str, expires: datetime | None, failure: str, now: datetime
) -> tuple[str, str]:
    if failure == "expired":
        return "錯誤", f"{domain} 已過期"
    if failure == "mismatch":
        return "錯誤", f"{domain} 憑證的網域對不上"
    if failure == "unreachable" or (expires is None and not failure):
        return "警告", f"{domain} 連不上 127.0.0.1:443，沒有查到憑證"
    if expires is None:
        return "錯誤", f"{domain} 憑證驗證失敗 ({failure})"
    days = (expires - now).days
    summary = f"剩下 {days} 天，{expires:%Y-%m-%d} 到期"
    if days < CERT_WARNING_DAYS:
        return "警告", f"{domain} ({summary}；自動更新可能沒有在運作)"
    return "正常", f"{domain} ({summary})"


def probe_certificate(domain: str) -> tuple[datetime | None, str]:
    """對本機的 443 用這個網域實際連一次: 查到的是現在真的在用的那張憑證。

    憑證檔在 /etc/letsencrypt 底下只有 root 讀得到, 所以不讀檔。
    """
    context = ssl.create_default_context()
    try:
        with (
            socket.create_connection(("127.0.0.1", 443), timeout=5) as raw,
            context.wrap_socket(raw, server_hostname=domain) as tls,
        ):
            not_after = str((tls.getpeercert() or {}).get("notAfter", ""))
    except ssl.SSLCertVerificationError as error:
        # OpenSSL 的驗證代碼: 10 是過期, 62 是網域不符。
        known = {10: "expired", 62: "mismatch"}
        return None, known.get(error.verify_code, error.verify_message)
    except OSError:
        return None, "unreachable"
    if not not_after:
        return None, "unreachable"
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), timezone.utc), ""


def nginx_binary() -> str | None:
    # 一般帳號的 PATH 不一定有 /usr/sbin。
    return shutil.which("nginx") or next(
        (path for path in ("/usr/sbin/nginx", "/usr/local/sbin/nginx") if Path(path).is_file()),
        None,
    )


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    except OSError:
        return None


def _read_include(pattern: str) -> str | None:
    base = Path(pattern) if pattern.startswith("/") else HOST_NGINX_DIR / pattern
    contents = [_read(path) for path in sorted(base.parent.glob(base.name))]
    return "\n".join(content for content in contents if content) or None


def check_host_nginx(env: dict[str, str]) -> None:
    binary = nginx_binary()
    if binary is None:
        record("正常", "Nginx", "未安裝")
        return
    # `nginx -v` 把版本印在 stderr。
    output = subprocess.run([binary, "-v"], capture_output=True, text=True, check=False).stderr
    version = re.search(r"nginx/(\S+)", output)
    record("正常", "Nginx", version.group(1) if version else "版本讀不到")

    files: dict[str, str] = {}
    for directory, pattern in (("sites-enabled", "*"), ("conf.d", "*.conf")):
        for path in sorted((HOST_NGINX_DIR / directory).glob(pattern)):
            content = _read(path)
            if content is not None:
                files[path.name] = content
    http = _read(HOST_NGINX_DIR / "nginx.conf") or ""
    lines, domains = host_nginx_lines(files, env.get("SYSTEM_PORT", "3000"), _read_include, http)
    results.extend(lines)
    now = datetime.now(timezone.utc)
    for domain in domains:
        record(*_cert_result(domain, now))


def _cert_result(domain: str, now: datetime) -> Result:
    status, detail = certificate_line(domain, *probe_certificate(domain), now)
    return status, "Cert", detail


def run(_name: str, args: list[str]) -> None:
    if args:
        fail("用法：make doctor")
    env = load_env()
    name = env.get("SYSTEM_NAME") or env.get("COMPOSE_PROJECT_NAME", "")
    record("正常", "System", f"{name} v{app_version()} ({env.get('MODE', '')})")
    check_docker()
    check_journal(env)
    check_host_nginx(env)
    check_env(env)
    if any(container_running(env, service) for service in SERVICES):
        if check_services(env):
            check_runtime(env)
    else:
        record("警告", "service", "沒有在執行 (make start)")

    print("\n".join(render(results)))
    if any(status == "錯誤" for status, _, _ in results):
        raise SystemExit(1)
