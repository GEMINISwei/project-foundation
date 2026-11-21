"""`wait-ci.sh`: 等本機 HEAD 那個 commit 的 CI 與 PR 兩個 workflow 跑完。

`gh pr checks --watch` 只看當下已經出現的檢查: push 之後 CI 的 run 還沒建立就結束,
GitHub 還沒收到 push 時看的是上一個 commit 早就通過的結果。兩種都會讓 agent 以為全綠。
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/wait-ci.sh"
SHA = "a" * 40
MAX_WAITING = 10
MAX_FAILURES = 10
FAKE_GH = """#!/usr/bin/env python3
# run list: 依序取出該 workflow 的下一個回應 (用完就重複最後一個);
# "" 代表還沒有 run, "FAIL" 代表查詢失敗, 其餘是 "<id> <status> <conclusion>"。
# run view: 印出該 run 失敗的 job。
import json, os, sys
state_path = os.path.join(os.environ["FAKE_DIR"], "state.json")
with open(state_path) as f:
    state = json.load(f)
args = sys.argv[1:]
state["calls"].append(args)
if args[:2] == ["run", "list"]:
    assert args[args.index("--commit") + 1] == os.environ["FAKE_HEAD"]
    queue = state["runs"][args[args.index("--workflow") + 1]]
    answer = queue.pop(0) if len(queue) > 1 else queue[0]
elif args[:2] == ["run", "view"]:
    answer = state["failed_jobs"].get(args[2], "")
else:
    answer = "FAIL"
with open(state_path, "w") as f:
    json.dump(state, f)
if answer == "FAIL":
    print("network down", file=sys.stderr)
    sys.exit(1)
if answer:
    print(answer)
"""
FAKE_GIT = """#!/bin/sh
case "$2" in
    HEAD) echo "$FAKE_HEAD" ;;
    *) [ -n "$FAKE_UPSTREAM" ] || exit 128; echo "$FAKE_UPSTREAM" ;;
esac
"""


def wait(
    tmp_path: Path,
    ci: list[str],
    pr: list[str],
    *,
    failed_jobs: dict[str, str] | None = None,
    upstream: str = SHA,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gh", FAKE_GH), ("git", FAKE_GIT)):
        (bin_dir / name).write_text(body, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    state = {"runs": {"CI": ci, "PR": pr}, "failed_jobs": failed_jobs or {}, "calls": []}
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    env.update(FAKE_DIR=str(tmp_path), FAKE_HEAD=SHA, FAKE_UPSTREAM=upstream)
    result = subprocess.run(
        [str(SCRIPT), "0"], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    calls = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["calls"]
    return result, calls


def test_waits_until_both_workflows_have_runs_and_finish(tmp_path: Path) -> None:
    result, _ = wait(
        tmp_path,
        ci=["", "", "1 in_progress ", "1 completed success"],
        pr=["2 completed success"],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["CI success 1", "PR success 2"]


def test_a_finished_pr_check_alone_is_not_success(tmp_path: Path) -> None:
    # 只等到 PR 這個 workflow 就結束, 正是 `gh pr checks --watch` 出錯的情況。
    result, calls = wait(tmp_path, ci=[""], pr=["2 completed success"])

    assert result.returncode == 2
    assert "CI" in result.stderr
    assert sum(call[:2] == ["run", "list"] for call in calls) == 2 * MAX_WAITING


def test_stops_as_soon_as_a_job_fails(tmp_path: Path) -> None:
    result, _ = wait(
        tmp_path,
        ci=["1 in_progress "],
        pr=["2 in_progress "],
        failed_jobs={"1": "lint,e2e (1/1)"},
    )

    assert result.returncode == 1
    assert result.stdout.splitlines() == ["CI failure 1 lint,e2e (1/1)"]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled"])
def test_a_run_that_did_not_succeed_is_reported(tmp_path: Path, conclusion: str) -> None:
    result, _ = wait(
        tmp_path,
        ci=["1 completed success"],
        pr=[f"2 completed {conclusion}"],
        failed_jobs={"2": "pr"},
    )

    assert result.returncode == 1
    assert result.stdout.splitlines() == [f"PR {conclusion} 2 pr"]


@pytest.mark.parametrize("upstream", ["b" * 40, ""])
def test_refuses_a_head_that_is_not_pushed(tmp_path: Path, upstream: str) -> None:
    # 沒 push 的 commit 不會有 run, 等下去只會等到逾時。
    result, calls = wait(
        tmp_path, ci=["1 completed success"], pr=["2 completed success"], upstream=upstream
    )

    assert result.returncode == 2
    assert "push" in result.stderr
    assert calls == []


def test_stops_at_once_when_the_first_query_fails(tmp_path: Path) -> None:
    # 第一次就失敗多半是沒登入或不在 repo 裡: 重試也不會好。
    result, calls = wait(tmp_path, ci=["FAIL", "1 completed success"], pr=["2 completed success"])

    assert result.returncode == 2
    assert len(calls) == 1


def test_keeps_waiting_through_temporary_failures(tmp_path: Path) -> None:
    result, _ = wait(
        tmp_path,
        ci=["1 in_progress ", "FAIL", "FAIL", "1 completed success"],
        pr=["2 completed success"],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["CI success 1", "PR success 2"]
    assert "network down" in result.stderr


def test_gives_up_after_too_many_consecutive_failures(tmp_path: Path) -> None:
    result, _ = wait(
        tmp_path,
        ci=["1 in_progress ", *["FAIL"] * MAX_FAILURES, "1 completed success"],
        pr=["2 completed success"],
    )

    assert result.returncode == 2
    assert result.stdout == ""
