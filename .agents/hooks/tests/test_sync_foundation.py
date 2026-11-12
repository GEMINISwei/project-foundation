"""`sync-foundation` 的腳本: 把 foundation 從上次同步之後的改動帶進子專案。

子專案與 foundation 沒有共同的 git 歷史 (main 一律 squash, 也可能是用 template 建立的), 不能 merge。
腳本靠 `.foundation.json` 記下的 commit 當基準做三方比對: 分類錯了不會有任何檢查變紅,
子專案的改動被蓋掉、或 foundation 的修正被安靜地跳過, 都要等到出事才看得出來。

"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support import REPO_ROOT

GIT = shutil.which("git") or "git"
SCRIPT = REPO_ROOT / ".agents/skills/sync-foundation/scripts/sync.py"
# 不讀開發者自己的 git 設定 (簽章、hooksPath、預設分支名稱)。
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
INITIAL = {
    "Makefile": "all:\n\techo foundation\n",
    "README.md": "# Foundation\n",
    "CHANGELOG.md": "# 變更紀錄\n",
    "docs/foundation/guide.md": "第一行\n第二行\n第三行\n第四行\n第五行\n",
    "apps/api/app/main.py": "A = 1\nB = 2\nC = 3\nD = 4\nE = 5\n",
    "apps/api/app/version.py": 'APP_VERSION = "0.0.0"\n',
    "tools/old.py": "OLD = True\n",
}


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [GIT, *args], cwd=repo, env=ENV, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def write(repo: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def new_repo(path: Path, files: dict[str, str]) -> Path:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "symbolic-ref", "HEAD", "refs/heads/main")
    write(path, files)
    commit(path, "init")
    return path


def sync(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def record(repo: Path) -> dict[str, str]:
    data: dict[str, str] = json.loads((repo / ".foundation.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture
def foundation(tmp_path: Path) -> Path:
    return new_repo(tmp_path / "foundation", INITIAL)


@pytest.fixture
def child(tmp_path: Path, foundation: Path) -> Path:
    """內容與 foundation 相同、但沒有共同歷史的 repo, 已經記下同步點。"""
    repo = new_repo(tmp_path / "child", INITIAL)
    assert sync(repo, "init", str(foundation)).returncode == 0
    commit(repo, "record foundation")
    return repo


def test_init_records_repo_and_current_foundation_commit(tmp_path: Path, foundation: Path) -> None:
    repo = new_repo(tmp_path / "child", INITIAL)

    result = sync(repo, "init", str(foundation))

    assert result.returncode == 0, result.stderr
    assert record(repo) == {"repo": str(foundation), "commit": git(foundation, "rev-parse", "HEAD")}


def test_init_accepts_an_explicit_commit(tmp_path: Path, foundation: Path) -> None:
    first = git(foundation, "rev-parse", "HEAD")
    write(foundation, {"Makefile": "all:\n\techo newer\n"})
    commit(foundation, "newer")
    repo = new_repo(tmp_path / "child", INITIAL)

    assert sync(repo, "init", str(foundation), first).returncode == 0

    assert record(repo)["commit"] == first


def test_init_refuses_to_overwrite_an_existing_record(child: Path, foundation: Path) -> None:
    before = record(child)

    result = sync(child, "init", str(foundation))

    assert result.returncode != 0
    assert record(child) == before


@pytest.mark.parametrize("command", ["plan", "apply"])
def test_without_record_explains_how_to_initialize(foundation: Path, command: str) -> None:
    # foundation 本身沒有同步紀錄: 在這裡執行要停下來, 不是把自己當成子專案。
    result = sync(foundation, command)

    assert result.returncode != 0
    assert ".foundation.json" in result.stderr
    assert "init" in result.stderr


def test_plan_reports_up_to_date_when_foundation_has_not_changed(child: Path) -> None:
    result = sync(child, "plan")

    assert result.returncode == 0, result.stderr
    assert "已經是最新" in result.stdout


def test_plan_lists_changes_without_touching_anything(child: Path, foundation: Path) -> None:
    write(foundation, {"Makefile": "all:\n\techo changed\n"})
    commit(foundation, "fix: 修正 make")
    before = record(child)

    result = sync(child, "plan")

    assert result.returncode == 0, result.stderr
    assert "Makefile" in result.stdout
    assert "fix: 修正 make" in result.stdout
    assert (child / "Makefile").read_text(encoding="utf-8") == INITIAL["Makefile"]
    assert record(child) == before
    assert git(child, "status", "--porcelain") == ""


def test_apply_adopts_files_the_child_did_not_change(child: Path, foundation: Path) -> None:
    write(foundation, {"Makefile": "all:\n\techo changed\n"})
    commit(foundation, "change")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    assert (child / "Makefile").read_text(encoding="utf-8") == "all:\n\techo changed\n"


def test_apply_adds_new_files_and_removes_deleted_ones(child: Path, foundation: Path) -> None:
    write(foundation, {"tools/new.py": "NEW = True\n"})
    (foundation / "tools/old.py").unlink()
    commit(foundation, "replace")

    assert sync(child, "apply").returncode == 0

    assert (child / "tools/new.py").read_text(encoding="utf-8") == "NEW = True\n"
    assert not (child / "tools/old.py").exists()


def test_apply_keeps_the_executable_bit(child: Path, foundation: Path) -> None:
    write(foundation, {"tools/run.sh": "#!/bin/sh\n"})
    (foundation / "tools/run.sh").chmod(0o755)
    commit(foundation, "add script")

    assert sync(child, "apply").returncode == 0

    assert os.access(child / "tools/run.sh", os.X_OK)


def test_apply_merges_changes_that_do_not_overlap(child: Path, foundation: Path) -> None:
    write(foundation, {"apps/api/app/main.py": "A = 10\nB = 2\nC = 3\nD = 4\nE = 5\n"})
    commit(foundation, "change first line")
    write(child, {"apps/api/app/main.py": "A = 1\nB = 2\nC = 3\nD = 4\nE = 50\n"})
    commit(child, "change last line")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    merged = (child / "apps/api/app/main.py").read_text(encoding="utf-8")
    assert merged == "A = 10\nB = 2\nC = 3\nD = 4\nE = 50\n"
    assert "自動合併" in result.stdout


def test_apply_leaves_conflict_markers_and_reports_the_file(child: Path, foundation: Path) -> None:
    write(foundation, {"apps/api/app/main.py": "A = 10\nB = 2\nC = 3\nD = 4\nE = 5\n"})
    commit(foundation, "foundation side")
    write(child, {"apps/api/app/main.py": "A = 99\nB = 2\nC = 3\nD = 4\nE = 5\n"})
    commit(child, "child side")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    merged = (child / "apps/api/app/main.py").read_text(encoding="utf-8")
    assert "<<<<<<<" in merged
    assert "A = 99" in merged
    assert "A = 10" in merged
    assert "衝突" in result.stdout
    assert "apps/api/app/main.py" in result.stdout


def test_apply_does_not_carry_project_owned_files(child: Path, foundation: Path) -> None:
    write(
        foundation,
        {
            "README.md": "# Foundation v2\n",
            "CHANGELOG.md": "# 變更紀錄\n\n- foundation 的紀錄\n",
            "apps/api/app/version.py": 'APP_VERSION = "9.9.9"\n',
            "docs/project/README.md": "foundation 的說明\n",
        },
    )
    commit(foundation, "touch project-owned files")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    for name in ("README.md", "CHANGELOG.md", "apps/api/app/version.py"):
        assert (child / name).read_text(encoding="utf-8") == INITIAL[name]
    assert not (child / "docs/project/README.md").exists()


def test_apply_keeps_child_edits_when_foundation_deletes_the_file(
    child: Path, foundation: Path
) -> None:
    (foundation / "tools/old.py").unlink()
    commit(foundation, "delete")
    write(child, {"tools/old.py": "OLD = False\n"})
    commit(child, "edit")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    assert (child / "tools/old.py").read_text(encoding="utf-8") == "OLD = False\n"
    assert "tools/old.py" in result.stdout
    assert "需要判斷" in result.stdout


def test_apply_reports_when_both_sides_added_different_files(child: Path, foundation: Path) -> None:
    write(foundation, {"tools/new.py": "FROM = 'foundation'\n"})
    commit(foundation, "add")
    write(child, {"tools/new.py": "FROM = 'child'\n"})
    commit(child, "add")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    assert (child / "tools/new.py").read_text(encoding="utf-8") == "FROM = 'child'\n"
    assert "tools/new.py" in result.stdout
    assert "需要判斷" in result.stdout


def test_apply_skips_changes_the_child_already_has(child: Path, foundation: Path) -> None:
    changed = {"Makefile": "all:\n\techo same fix\n"}
    write(foundation, changed)
    commit(foundation, "fix")
    write(child, changed)
    commit(child, "same fix")

    result = sync(child, "apply")

    assert result.returncode == 0, result.stderr
    assert git(child, "status", "--porcelain") == "M .foundation.json"


def test_apply_moves_the_record_to_the_synced_commit(child: Path, foundation: Path) -> None:
    write(foundation, {"Makefile": "all:\n\techo changed\n"})
    head = commit(foundation, "change")

    assert sync(child, "apply").returncode == 0

    assert record(child) == {"repo": str(foundation), "commit": head}
    commit(child, "sync")
    assert "已經是最新" in sync(child, "plan").stdout


def test_apply_refuses_a_dirty_worktree(child: Path, foundation: Path) -> None:
    # 同步的結果要能單獨看 diff: 混進還沒 commit 的改動就分不出哪些是 foundation 帶來的。
    write(foundation, {"Makefile": "all:\n\techo changed\n"})
    commit(foundation, "change")
    write(child, {"apps/api/app/main.py": "A = 0\n"})
    before = record(child)

    result = sync(child, "apply")

    assert result.returncode != 0
    assert (child / "Makefile").read_text(encoding="utf-8") == INITIAL["Makefile"]
    assert record(child) == before


def test_plan_lists_child_edits_to_foundation_owned_files(child: Path, foundation: Path) -> None:
    # foundation 這段期間沒動到的檔案也要列: 在子專案直接修基礎建設, 修正就回不到 foundation。
    write(foundation, {"Makefile": "all:\n\techo changed\n"})
    commit(foundation, "change")
    write(child, {"docs/foundation/guide.md": "子專案改過\n", "apps/api/app/main.py": "A = 0\n"})
    commit(child, "edit")

    result = sync(child, "plan")

    assert result.returncode == 0, result.stderr
    drift = result.stdout.split("歸 foundation", 1)[1]
    assert "docs/foundation/guide.md" in drift
    assert "apps/api/app/main.py" not in drift


def test_fails_when_recorded_commit_is_not_in_foundation(child: Path, foundation: Path) -> None:
    data = record(child)
    data["commit"] = "0" * 40
    (child / ".foundation.json").write_text(json.dumps(data), encoding="utf-8")
    commit(child, "break record")

    result = sync(child, "plan")

    assert result.returncode != 0
    assert "找不到" in result.stderr
