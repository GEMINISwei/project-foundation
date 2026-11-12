"""make 指令裡會刪檔、會決定能不能部署的那幾段邏輯。"""

from pathlib import Path

import pytest
from tools import backups, compose
from tools.commands import check, release
from tools.env import parse_env_file


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
    """假裝 nginx 與 worker 在執行, 記下對 docker 下的 stop / start。"""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(compose, "container_running", lambda _env, name: name != "web")
    monkeypatch.setattr(compose, "wait_until_ready", lambda _env, _services: {})
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
        ("stop", "app-worker"),
        ("start", "app-worker"),
        ("start", "app-nginx"),
    ]


def test_a_failed_backup_resumes_services_but_a_failed_restore_leaves_them_stopped(docker_calls):
    with pytest.raises(RuntimeError), compose.paused(ENV, ("nginx",), resume_on_failure=True):
        raise RuntimeError("backup failed")
    assert docker_calls == [("stop", "app-nginx"), ("start", "app-nginx")]

    docker_calls.clear()
    with pytest.raises(RuntimeError), compose.paused(ENV, ("nginx",), resume_on_failure=False):
        raise RuntimeError("restore failed")
    assert docker_calls == [("stop", "app-nginx")]
