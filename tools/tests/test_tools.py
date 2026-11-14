"""make 指令裡會刪檔、會決定能不能部署的那幾段邏輯。"""

import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tools import backups, compose
from tools.commands import check, doctor, logs, release
from tools.env import REPO_ROOT, parse_env_file


def touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text("x")


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(backups, "BACKUP_DIR", tmp_path)
    return tmp_path


def test_env_file_is_read_the_way_docker_compose_reads_it(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# 註解\n"
        "\n"
        "SYSTEM_NAME=My App\n"
        'QUOTED="a # b"\n'
        "INLINE=value # 說明\n"
        "EMPTY=\n"
        "export EXPORTED=1\n"
        "URL=postgres://u:p@h/db?x=1#frag\n"
    )
    assert parse_env_file(path) == {
        "SYSTEM_NAME": "My App",
        "QUOTED": "a # b",
        "INLINE": "value",
        "EMPTY": "",
        "EXPORTED": "1",
        # 沒有空白的 # 是值的一部分, 不是註解。
        "URL": "postgres://u:p@h/db?x=1#frag",
    }


def test_backup_names_carry_version_and_time(backup_dir):
    backup = backups.parse(backup_dir / "my-app_v1.2.3_20261111_093000.dump")
    assert backup is not None
    assert (backup.version, backup.kind, backup.label) == (
        "1.2.3",
        "dump",
        "v1.2.3 2026-11-11 09:30:00",
    )
    assert backups.parse(backup_dir / "notes.txt") is None
    assert backups.parse(backup_dir / "my-app_v1.2_20261111_093000.dump") is None


def test_listing_is_newest_first_and_can_be_limited_to_one_version(backup_dir):
    touch(
        backup_dir,
        "app_v1.0.0_20261101_000000.dump",
        "app_v1.1.0_20261103_000000.dump",
        "app_v1.1.0_20261102_000000.dump",
        "app_v1.1.0_20261103_000000.tar",
        "unrelated.dump",
    )
    assert [b.path.name for b in backups.list_backups("dump")] == [
        "app_v1.1.0_20261103_000000.dump",
        "app_v1.1.0_20261102_000000.dump",
        "app_v1.0.0_20261101_000000.dump",
    ]
    assert len(backups.list_backups("dump", "1.0.0")) == 1


def test_prune_removes_whole_sets_and_never_touches_other_files(backup_dir):
    for stamp in ("20261101_000000", "20261102_000000", "20261103_000000"):
        touch(
            backup_dir,
            f"app_v1.0.0_{stamp}.dump",
            f"app_v1.0.0_{stamp}.tar",
            f"app_v1.0.0_{stamp}.logs.tar.gz",
        )
    touch(backup_dir, "manual-copy.dump", "README.md")

    doomed = [path.name for path in backups.to_prune(2)]

    assert doomed == [
        "app_v1.0.0_20261101_000000.dump",
        "app_v1.0.0_20261101_000000.logs.tar.gz",
        "app_v1.0.0_20261101_000000.tar",
    ]
    assert backups.to_prune(3) == []


def migration(directory: Path, revision: str) -> None:
    (directory / f"{revision}.py").write_text(
        f'revision: str = "{revision}"\ndown_revision = None\n'
    )


def test_deploy_is_allowed_when_the_database_is_at_a_known_revision(tmp_path, capsys):
    migration(tmp_path, "aaa111")
    migration(tmp_path, "bbb222")
    check.check_migration_direction(str(tmp_path), "aaa111")
    check.check_migration_direction(str(tmp_path), "")  # 全新的資料庫
    assert "放行" in capsys.readouterr().out


def test_deploy_is_refused_when_the_database_is_ahead_of_the_code(tmp_path):
    migration(tmp_path, "aaa111")
    with pytest.raises(SystemExit):
        check.check_migration_direction(str(tmp_path), "zzz999")


def test_versions_are_compared_as_numbers_not_text():
    assert release.as_numbers("0.10.0") > release.as_numbers("0.9.0")
    assert release.VERSION_PATTERN.match("1.2.3")
    assert not release.VERSION_PATTERN.match("01.2.3")
    assert not release.VERSION_PATTERN.match("1.2")


def test_unreleased_section_stops_at_the_next_version():
    changelog = "# 變更紀錄\n\n## [Unreleased]\n\n- 新功能\n\n## [0.1.0]\n\n- 舊的\n"
    assert release.unreleased_entries(changelog) == "- 新功能"
    assert release.unreleased_entries("## [Unreleased]\n\n## [0.1.0]\n- 舊的\n") == ""


def test_nginx_and_compose_safety_rules_hold_for_this_repo():
    # 綁 loopback、每個轉送的 location 都覆寫標頭: 這兩條壞了不會有任何症狀。
    check.lint_infra()


def test_a_service_is_ready_only_when_running_and_past_its_healthcheck():
    assert compose.is_ready("healthy")
    assert compose.is_ready("running")  # 沒有 healthcheck 的服務
    for state in ("starting", "unhealthy", "restarting", "exited", "missing"):
        assert not compose.is_ready(state)


@pytest.fixture
def docker_calls(monkeypatch):
    """假裝 web 以外的容器都在執行, 記下對 docker 下的 stop / start。"""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compose, "running_containers", lambda: {"app-nginx", "app-worker-1", "app-worker-2"}
    )
    monkeypatch.setattr(compose, "wait_for_containers", lambda _names: {})
    monkeypatch.setattr(
        compose.subprocess, "run", lambda command, **_: calls.append((command[1], command[2]))
    )
    return calls


ENV = {"COMPOSE_PROJECT_NAME": "app"}


def test_paused_services_come_back_in_reverse_order_and_stopped_ones_stay_stopped(docker_calls):
    with compose.paused(ENV, ("nginx", "web", "worker"), resume_on_failure=True):
        pass
    assert docker_calls == [
        ("stop", "app-nginx"),
        ("stop", "app-worker-1"),
        ("start", "app-worker-1"),
        ("start", "app-nginx"),
    ]


def test_paused_services_cover_every_worker_replica(docker_calls):
    # 備份時有一份 worker 沒停, 資料庫與上傳的檔案就不是同一個時間點。
    with compose.paused({**ENV, "WORKER_REPLICAS": "2"}, ("worker",), resume_on_failure=True):
        pass
    assert docker_calls == [
        ("stop", "app-worker-1"),
        ("stop", "app-worker-2"),
        ("start", "app-worker-2"),
        ("start", "app-worker-1"),
    ]


def test_readiness_waits_for_every_worker_replica(monkeypatch):
    states = {"app-api": "healthy", "app-worker-1": "healthy", "app-worker-2": "starting"}
    monkeypatch.setattr(compose, "container_state", lambda name: states.get(name, "missing"))
    env = {**ENV, "WORKER_REPLICAS": "3"}
    assert compose.wait_until_ready(env, ("api", "worker"), timeout=0) == {
        "app-worker-2": "starting",
        "app-worker-3": "missing",
    }


def test_logs_include_every_worker_replica(monkeypatch):
    read: list[str] = []

    def fake_run(command, **_kwargs):
        read.append(command[-1])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(logs.subprocess, "run", fake_run)
    env = {**ENV, "MODE": "production", "WORKER_REPLICAS": "2"}
    logs.read_logs(env, "worker", None)
    assert read == ["app-worker-1", "app-worker-2"]


def test_api_memory_limit_is_512m_for_one_process():
    assert compose.api_memory_limit({"API_PROCESSES": "1"}) == "512M"


def test_api_memory_limit_grows_256m_per_extra_process():
    assert compose.api_memory_limit({"API_PROCESSES": "2"}) == "768M"
    assert compose.api_memory_limit({"API_PROCESSES": "4"}) == "1280M"


def test_api_memory_limit_defaults_to_one_process():
    assert compose.api_memory_limit({}) == "512M"
    assert compose.api_memory_limit({"API_PROCESSES": ""}) == "512M"


def test_compose_passes_api_memory_limit(monkeypatch):
    seen: dict[str, str] = {}
    monkeypatch.setattr(compose.subprocess, "run", lambda _command, *, env, **_: seen.update(env))
    compose.compose({**ENV, "MODE": "production", "API_PROCESSES": "3"}, "config")
    assert seen["API_MEMORY_LIMIT"] == "1024M"


@pytest.mark.parametrize("name", ["API_PROCESSES", "WORKER_REPLICAS"])
@pytest.mark.parametrize("value", ["0", "-1", "two", "1.5"])
def test_invalid_process_or_replica_count_is_refused(name, value):
    with pytest.raises(SystemExit):
        compose.check_capacity({name: value})


def test_too_many_database_connections_are_refused():
    # 每個行程的連線池最多 15 條, PostgreSQL 預設 100 條還要留給維運。
    compose.check_capacity({"API_PROCESSES": "4", "WORKER_REPLICAS": "2"})
    with pytest.raises(SystemExit):
        compose.check_capacity({"API_PROCESSES": "4", "WORKER_REPLICAS": "3"})


def test_backup_directory_is_private_to_its_owner(backup_dir):
    # 備份檔裡有密碼雜湊與 AUDIT: 主機上的其他帳號不該讀得到, 既有的目錄也要收緊。
    backup_dir.chmod(0o755)
    backups.ensure_private_dir()
    assert backup_dir.stat().st_mode & 0o777 == 0o700

    backup_dir.rmdir()
    backups.ensure_private_dir()
    assert backup_dir.stat().st_mode & 0o777 == 0o700


def test_a_failed_backup_resumes_services_but_a_failed_restore_leaves_them_stopped(docker_calls):
    with pytest.raises(RuntimeError), compose.paused(ENV, ("nginx",), resume_on_failure=True):
        raise RuntimeError("backup failed")
    assert docker_calls == [("stop", "app-nginx"), ("start", "app-nginx")]

    docker_calls.clear()
    with pytest.raises(RuntimeError), compose.paused(ENV, ("nginx",), resume_on_failure=False):
        raise RuntimeError("restore failed")
    assert docker_calls == [("stop", "app-nginx")]


# 用另一個行程跑: 進入點會動到行程自己的 stdin 與輸出, 不能在測試的行程裡做。
PREPARE = "from tools.__main__ import prepare_streams; prepare_streams(); "


def run_python(code: str, answer: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", PREPARE + code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        input=answer,
    )


def test_a_command_does_not_swallow_the_script_that_runs_it():
    # 部署腳本經 ssh 的 stdin 交給 bash 逐行執行: 子行程讀了 stdin, 後面的步驟就消失而且不報錯。
    child = "import subprocess; subprocess.run(['cat'], stdout=subprocess.DEVNULL)"
    script = f"set -e\n{sys.executable} -c {shlex.quote(PREPARE + child)}\necho AFTER\n"
    result = subprocess.run(
        ["bash", "-s"], input=script, cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout == "AFTER\n"


def test_a_piped_answer_still_reaches_the_confirmation_prompt():
    code = "from tools.env import confirm; confirm('確定？'); print('confirmed')"
    result = run_python(code, answer="y\n")
    assert result.stdout.endswith("confirmed\n")


def test_messages_come_out_in_the_order_things_happened():
    # 輸出被接走時 (ssh、CI) Python 預設整塊緩衝, 子行程的輸出會跑到前面。
    result = run_python("import subprocess; print('first'); subprocess.run(['echo', 'second'])")
    assert result.stdout == "first\nsecond\n"


JOURNAL_DENIED = subprocess.CompletedProcess(
    args=[],
    returncode=0,
    stdout="-- No entries --\n",
    stderr=(
        "Hint: You are currently not seeing messages from other users and the system.\n"
        "      Users in groups 'adm', 'systemd-journal' can see all messages.\n"
    ),
)
JOURNALD_ENV = {"COMPOSE_PROJECT_NAME": "app", "MODE": "production", "LOG_DRIVER": "journald"}


@pytest.fixture
def unreadable_journal(monkeypatch):
    monkeypatch.setattr(logs.shutil, "which", lambda _name: "/usr/bin/journalctl")
    monkeypatch.setattr(logs.subprocess, "run", lambda *_args, **_kwargs: JOURNAL_DENIED)
    monkeypatch.setattr(logs, "load_env", lambda: JOURNALD_ENV)


@pytest.mark.parametrize("args", [["trace", "58143613783be4fe"], ["errors"]])
def test_logs_say_so_when_the_journal_cannot_be_read(unreadable_journal, capsys, args):
    # 讀不到與「沒有紀錄」要分得出來: 後者會讓人以為沒事。
    with pytest.raises(SystemExit):
        logs.run("logs", args)
    captured = capsys.readouterr()
    assert "systemd-journal" in captured.err
    assert "找不到" not in captured.err
    assert "沒有錯誤" not in captured.out


def test_doctor_checks_every_worker_replica(monkeypatch):
    lines = ["api\trunning\thealthy", "worker\trunning\thealthy", "worker\texited\t"]
    output = subprocess.CompletedProcess([], 0, stdout="\n".join(lines) + "\n", stderr="")
    monkeypatch.setattr(doctor, "compose", lambda *_args, **_kwargs: output)
    monkeypatch.setattr(doctor, "job_counts", lambda _env: None)
    monkeypatch.setattr(doctor, "results", [])
    assert not doctor.check_services(ENV)
    assert ("錯誤", "worker") in [(status, name) for status, name, _ in doctor.results]


def test_doctor_reports_a_journal_it_cannot_read(unreadable_journal, monkeypatch):
    monkeypatch.setattr(doctor, "results", [])
    doctor.check_journal(JOURNALD_ENV)
    assert [(status, name) for status, name, _ in doctor.results] == [("錯誤", "Log")]


def test_doctor_output_is_grouped_and_aligned():
    lines = doctor.render(
        [
            ("正常", "System", "My App v0.2.1 (production)"),
            ("正常", "nginx", "執行中"),
            ("警告", "Header", "缺少 X-Forwarded-Proto (cookie 不會帶 Secure)"),
            # 資料庫結構要等服務檢查完才讀得到, 但屬於第一區。
            ("正常", "Database", "2f478491f1fa"),
            ("正常", "postgres", "執行中"),
        ]
    )
    assert lines == [
        "架構環境",
        "[正常] System    My App v0.2.1 (production)",
        "[正常] Database  2f478491f1fa",
        "",
        "容器服務",
        "[正常] nginx     執行中",
        "[正常] postgres  執行中",
        "",
        "Nginx 相關",
        "[警告] Header    缺少 X-Forwarded-Proto (cookie 不會帶 Secure)",
    ]


def test_doctor_summarises_workers_and_jobs_on_one_line():
    running = ("running", "healthy")
    assert doctor.worker_line([running, running], (0, 0)) == (
        "正常",
        "2 支運轉中、待處理 0 筆、失敗 0 筆",
    )
    assert doctor.worker_line([running, running], (20, 3)) == (
        "警告",
        "2 支運轉中、待處理 20 筆、失敗 3 筆 (make jobs list failed)",
    )
    status, detail = doctor.worker_line([running, ("exited", "")], (0, 0))
    assert (status, detail.split("、")[:2]) == ("錯誤", ["1 支運轉中", "1 支 exited"])
    # 資料庫讀不到時只報 worker 本身。
    assert doctor.worker_line([running], None) == ("正常", "1 支運轉中")


HOST_NGINX = """
server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl http2;
    server_name app.example.com;
    add_header Strict-Transport-Security "max-age=31536000" always;
    ssl_certificate /etc/letsencrypt/live/app.example.com/fullchain.pem;
    client_max_body_size 16m;
    location / {
        proxy_pass http://127.0.0.1:3000;   # 這套的 SYSTEM_PORT
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""


def test_doctor_finds_the_host_nginx_block_for_this_port():
    lines, domains = doctor.host_nginx_lines({"my-app": HOST_NGINX}, "3000")
    assert lines == [
        ("正常", "Host", "my-app → 127.0.0.1:3000"),
        ("正常", "Config", "X-Real-IP、X-Forwarded-Proto、上傳上限 16m、HSTS"),
    ]
    assert domains == ["app.example.com"]

    # 同主機的另一套系統: 別人的設定不能算成自己的。
    lines, domains = doctor.host_nginx_lines({"my-app": HOST_NGINX}, "3001")
    assert [(status, name) for status, name, _ in lines] == [("警告", "Host")]
    assert "127.0.0.1:3001" in lines[0][2]
    assert domains == []


def test_doctor_lists_each_missing_host_nginx_setting():
    without_proto_and_hsts = "\n".join(
        line
        for line in HOST_NGINX.splitlines()
        if "X-Forwarded-Proto" not in line and "Strict-Transport-Security" not in line
    )
    lines, _ = doctor.host_nginx_lines({"my-app": without_proto_and_hsts}, "3000")
    assert lines[:2] == [
        ("正常", "Host", "my-app → 127.0.0.1:3000"),
        ("正常", "Config", "X-Real-IP、上傳上限 16m"),
    ]
    assert [(status, name, detail.split(" ")[1]) for status, name, detail in lines[2:]] == [
        ("警告", "Header", "X-Forwarded-Proto"),
        ("警告", "Header", "HSTS"),
    ]

    bare = (
        "server { listen 443 ssl; server_name a.example.com; "
        "location / { proxy_pass http://localhost:3000; } }"
    )
    lines, _ = doctor.host_nginx_lines({"bare": bare}, "3000")
    assert [(status, name) for status, name, _ in lines] == [
        ("正常", "Host"),
        ("警告", "Header"),
        ("警告", "Header"),
        ("警告", "Upload"),
        ("警告", "Header"),
    ]

    # 還沒申請憑證: 只有 HTTP 的設定不檢查 HSTS, 也沒有憑證可以查。
    http_only = (
        "server { listen 80; server_name a.example.com; client_max_body_size 16m; "
        "location / { proxy_pass http://127.0.0.1:3000; proxy_set_header X-Real-IP $remote_addr; "
        "proxy_set_header X-Forwarded-Proto $scheme; } }"
    )
    lines, domains = doctor.host_nginx_lines({"plain": http_only}, "3000")
    assert [(status, name) for status, name, _ in lines] == [
        ("正常", "Host"),
        ("正常", "Config"),
        ("警告", "Cert"),
    ]
    assert domains == []


def test_doctor_follows_includes_in_the_host_nginx_config():
    # Ubuntu 內建的 /etc/nginx/proxy_params 就有這兩個標頭。
    included = {
        "proxy_params": "proxy_set_header X-Real-IP $remote_addr;\n"
        "proxy_set_header X-Forwarded-Proto $scheme;\n"
    }
    conf = """
    server {
        listen 443 ssl;
        server_name app.example.com;
        add_header Strict-Transport-Security "max-age=31536000" always;
        client_max_body_size 16m;
        location / {
            proxy_pass http://127.0.0.1:3000;
            include proxy_params;
        }
    }
    """
    lines, _ = doctor.host_nginx_lines({"my-app": conf}, "3000", include=included.get)
    assert [(status, name) for status, name, _ in lines] == [("正常", "Host"), ("正常", "Config")]


def test_doctor_reports_certificate_expiry_by_severity():
    now = datetime(2026, 11, 14, tzinfo=UTC)
    domain = "app.example.com"
    assert doctor.certificate_line(domain, now + timedelta(days=67), "", now) == (
        "正常",
        "app.example.com (剩下 67 天，2027-01-20 到期)",
    )
    # certbot 在剩 30 天時就會更新: 剩這麼少代表自動更新沒有在運作。
    assert doctor.certificate_line(domain, now + timedelta(days=10), "", now)[0] == "警告"
    assert doctor.certificate_line(domain, None, "expired", now)[0] == "錯誤"
    assert doctor.certificate_line(domain, None, "mismatch", now)[0] == "錯誤"
    # 連不上不等於憑證有問題。
    assert doctor.certificate_line(domain, None, "unreachable", now)[0] == "警告"


def test_doctor_skips_the_nginx_section_without_host_nginx(monkeypatch):
    monkeypatch.setattr(doctor, "nginx_binary", lambda: None)
    monkeypatch.setattr(doctor, "results", [])
    doctor.check_host_nginx({"SYSTEM_PORT": "3000"})
    assert doctor.results == [("正常", "Nginx", "未安裝")]
    assert "Nginx 相關" not in doctor.render(doctor.results)
