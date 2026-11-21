"""`wait-pr-closed.sh`: 在背景等 PR 離開 OPEN, 一次可能等上好幾天。

中途網路斷一下就結束, agent 會以為 PR 有變化而被叫醒; 反過來, 設定錯了 (號碼、沒登入)
卻一直重試, 就會無聲地永遠等下去。兩種都不會有任何檢查變紅。
"""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/wait-pr-closed.sh"
MAX_FAILURES = 10
FAKE_GH = """#!/bin/sh
# 依序回傳 responses 的每一行: FAIL 代表查詢失敗, 其餘原樣印出。
count=$(cat "$FAKE_DIR/count")
count=$((count + 1))
echo "$count" > "$FAKE_DIR/count"
line=$(sed -n "${count}p" "$FAKE_DIR/responses")
if [ "$line" = "FAIL" ]; then
    echo "network down $count" >&2
    exit 1
fi
echo "$line"
"""


def wait(tmp_path: Path, responses: list[str]) -> tuple[subprocess.CompletedProcess[str], int]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH, encoding="utf-8")
    gh.chmod(0o755)
    (tmp_path / "responses").write_text("\n".join(responses) + "\n", encoding="utf-8")
    (tmp_path / "count").write_text("0\n", encoding="utf-8")
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    env["FAKE_DIR"] = str(tmp_path)
    result = subprocess.run(
        [str(SCRIPT), "34", "0"], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    calls = int((tmp_path / "count").read_text(encoding="utf-8"))
    return result, calls


@pytest.mark.parametrize("state", ["MERGED", "CLOSED"])
def test_prints_the_final_state(tmp_path: Path, state: str) -> None:
    result, _ = wait(tmp_path, ["OPEN", "OPEN", state])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == state


@pytest.mark.parametrize("first", ["FAIL", "SOMETHING"])
def test_stops_at_once_when_the_first_query_fails(tmp_path: Path, first: str) -> None:
    # 第一次就失敗多半是號碼錯、沒登入: 重試也不會好, 要立刻讓 agent 知道。
    result, calls = wait(tmp_path, [first, "MERGED"])

    assert result.returncode != 0
    assert calls == 1


def test_keeps_waiting_through_temporary_failures(tmp_path: Path) -> None:
    result, _ = wait(tmp_path, ["OPEN", "FAIL", "FAIL", "OPEN", "MERGED"])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "MERGED"
    assert "network down 2" in result.stderr


def test_unexpected_output_is_a_failure_not_a_closed_pr(tmp_path: Path) -> None:
    result, _ = wait(tmp_path, ["OPEN", "", "MERGED"])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "MERGED"


def test_gives_up_after_too_many_consecutive_failures(tmp_path: Path) -> None:
    result, calls = wait(tmp_path, ["OPEN", *["FAIL"] * MAX_FAILURES, "MERGED"])

    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert calls == 1 + MAX_FAILURES
    assert f"network down {calls}" in result.stderr


def test_a_successful_query_resets_the_failure_count(tmp_path: Path) -> None:
    almost = ["FAIL"] * (MAX_FAILURES - 1)

    result, _ = wait(tmp_path, ["OPEN", *almost, "OPEN", *almost, "CLOSED"])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CLOSED"
