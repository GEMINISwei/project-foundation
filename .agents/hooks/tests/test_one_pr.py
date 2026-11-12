"""一次一個 PR: 使用者還有開著的 PR 時, agent 開新分支要先經過使用者同意。

規則在 docs/foundation/workflow.md〈一次一個 PR〉。只寫在文件時, agent 等合併的空檔最容易順手開
下一個分支, 後一個 PR 建立在還沒審過的程式上, 前一個一改就要跟著重做。

開著的 PR 由守衛問 gh, 這裡在 PATH 最前面放一個假的 gh, 不會真的連 GitHub。
同意的方式與測試鎖相同: Claude 跳確認; Codex 擋下, 由 agent 執行申請指令 (一定跳確認)。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_hooks import GUARD, HOOKS_DIR, git_repo

APPROVE = HOOKS_DIR / "approve.py"
APPROVE_COMMAND = "python3 .agents/hooks/approve.py branch"
APPROVAL_FILE = ".git/agent-approvals"
AGENTS = ("claude", "codex")
BLOCKED = {"claude": "ask", "codex": "deny"}

OPEN_PR = [{"number": 30, "headRefName": "docs/earlier-work"}]

NEW_BRANCH = [
    "git switch -c feat/next",
    "git switch --create feat/next",
    "git checkout -b feat/next",
    "git checkout -B feat/next origin/main",
    "git branch feat/next",
    "git worktree add ../next -b feat/next",
    "git worktree add ../next feat/next",
    "gh pr create --draft --title 'feat: next'",
    "git fetch -q && git switch -c feat/next origin/main",
]

OTHER_BRANCH_COMMANDS = [
    "git switch main",
    "git checkout main",
    "git checkout -- apps/api/app/config.py",
    "git branch",
    "git branch --list",
    "git branch -D feat/old",
    "git branch -m feat/renamed",
    "git branch --show-current",
    "git worktree list",
    "gh pr list --author @me --state open",
]


def fake_gh(tmp_path: Path, open_prs: list[dict[str, Any]] | None) -> dict[str, str]:
    """`gh pr list` 回傳 open_prs; None 表示 gh 查不到 (沒網路、沒登入)。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "gh"
    body = f"echo '{json.dumps(open_prs)}'" if open_prs is not None else "exit 1"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin"}


def decision(agent: str, command: str, repo: Path, env: dict[str, str]) -> str | None:
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    result = subprocess.run(
        [sys.executable, GUARD, agent],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=repo,
        env=env,
        check=True,
    )
    if not result.stdout.strip():
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecisionReason"], "擋下時要說明理由與下一步"
    return str(output["permissionDecision"])


def approve(repo: Path, *branches: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, APPROVE, "branch", *branches],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return git_repo(tmp_path / "repo", "docs/earlier-work")


@pytest.mark.parametrize("command", NEW_BRANCH)
@pytest.mark.parametrize("agent", AGENTS)
def test_new_branch_is_allowed_without_open_prs(
    agent: str, command: str, repo: Path, tmp_path: Path
) -> None:
    assert decision(agent, command, repo, fake_gh(tmp_path, [])) is None, f"誤擋: {command}"


@pytest.mark.parametrize("command", NEW_BRANCH)
@pytest.mark.parametrize("agent", AGENTS)
def test_new_branch_needs_approval_while_a_pr_is_open(
    agent: str, command: str, repo: Path, tmp_path: Path
) -> None:
    env = fake_gh(tmp_path, OPEN_PR)
    assert decision(agent, command, repo, env) == BLOCKED[agent], f"沒有攔下: {command}"


@pytest.mark.parametrize("command", OTHER_BRANCH_COMMANDS)
@pytest.mark.parametrize("agent", AGENTS)
def test_other_branch_commands_are_not_checked(
    agent: str, command: str, repo: Path, tmp_path: Path
) -> None:
    env = fake_gh(tmp_path, OPEN_PR)
    assert decision(agent, command, repo, env) is None, f"誤擋: {command}"


@pytest.mark.parametrize("agent", AGENTS)
def test_approved_branch_is_allowed_while_a_pr_is_open(
    agent: str, repo: Path, tmp_path: Path
) -> None:
    env = fake_gh(tmp_path, OPEN_PR)
    assert approve(repo, "fix/urgent").returncode == 0
    assert decision(agent, "git switch -c fix/urgent origin/main", repo, env) is None
    assert decision(agent, "git switch -c feat/other", repo, env) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_branch_approval_survives_new_commit(agent: str, repo: Path, tmp_path: Path) -> None:
    # 分支的放行針對名稱, 不像測試與防線檔案的放行一有新 commit 就失效。
    env = fake_gh(tmp_path, OPEN_PR)
    assert approve(repo, "fix/urgent").returncode == 0
    identity = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(
        ["git", *identity, "commit", "-q", "--allow-empty", "-m", "x"],
        cwd=repo,
        check=True,
    )
    assert decision(agent, "git switch -c fix/urgent origin/main", repo, env) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_pr_from_approved_branch_is_allowed(agent: str, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo", "fix/urgent")
    env = fake_gh(tmp_path, OPEN_PR)
    command = "gh pr create --draft --title 'fix: urgent'"
    assert decision(agent, command, repo, env) == BLOCKED[agent]
    assert approve(repo, "fix/urgent").returncode == 0
    assert decision(agent, command, repo, env) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_new_branch_is_allowed_when_open_prs_cannot_be_checked(
    agent: str, repo: Path, tmp_path: Path
) -> None:
    # 流程規則, 不是部署那種安全邊界: 沒網路時擋開分支只會礙事, 而且本來也開不了 PR。
    assert decision(agent, "git switch -c feat/next", repo, fake_gh(tmp_path, None)) is None


@pytest.mark.parametrize(
    "command",
    [
        f"echo '{{}}' > {APPROVAL_FILE}",
        f"touch {APPROVAL_FILE}",
        "./.agents/hooks/approve.py branch feat/next",
        "python .agents/hooks/approve.py branch feat/next",
        "cd apps && python3 ../.agents/hooks/approve.py branch feat/next",
    ],
)
@pytest.mark.parametrize("agent", AGENTS)
def test_guard_blocks_self_approval_of_parallel_branches(
    agent: str, command: str, repo: Path, tmp_path: Path
) -> None:
    assert decision(agent, command, repo, fake_gh(tmp_path, [])) == "deny", f"沒有擋下: {command}"


@pytest.mark.parametrize("agent", AGENTS)
def test_guard_allows_the_prompted_parallel_branch_approval(
    agent: str, repo: Path, tmp_path: Path
) -> None:
    command = f"{APPROVE_COMMAND} fix/urgent"
    assert decision(agent, command, repo, fake_gh(tmp_path, OPEN_PR)) is None
