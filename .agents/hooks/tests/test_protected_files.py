"""防線檔案: hook、agent 設定、CI 與檢查的設定, 改動前要使用者同意。

這些檔案決定了其他規則擋不擋得住: 刪掉一個 CI 步驟, required check 的名字還在, 照樣顯示綠燈;
在 `.claude/settings.local.json` 設 `disableAllHooks`, 所有 hook 就安靜地不生效。
它們有時確實要改, 所以不禁止, 而是一定讓使用者看到。

跟測試鎖不同, 不分實作前後: 防線檔案任何時候都不該被悄悄改掉。
同意的方式相同: Claude 跳確認; Codex 擋下, 由 agent 執行申請指令 (一定跳確認)。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from support import REPO_ROOT
from test_hooks import HOOKS_DIR
from test_test_guard import (
    AGENTS,
    BLOCKED,
    GUARD_COMMANDS,
    decision,
    git,
    run,
    write,
)

APPROVE = HOOKS_DIR / "approve.py"
APPROVAL_FILE = ".git/agent-approvals"

# 每一類各挑代表: 目錄底下的任何檔案都算, 單一檔案就是那一個。
PROTECTED = [
    ".agents/hooks/guard_commands.py",
    ".agents/hooks/ruff.toml",
    ".claude/settings.json",
    ".codex/hooks.json",
    ".codex/rules/publish-release.rules",
    ".githooks/commit-msg",
    ".github/workflows/ci.yml",
    ".github/scripts/check-pr.sh",
    "apps/api/pyproject.toml",
    "apps/web/package.json",
    "apps/web/eslint.config.mjs",
    "apps/web/.dependency-cruiser.cjs",
    "apps/web/knip.ts",
    "apps/web/tsconfig.json",
    "apps/web/vitest.config.ts",
    "tools/commands/check.py",
    "Makefile",
]
# 不進版控, 但在這裡設 disableAllHooks 就能關掉所有 hook。
LOCAL_ONLY = [".claude/settings.local.json"]

ORDINARY = [
    "AGENTS.md",
    "docs/foundation/testing.md",
    ".agents/skills/feature-workflow/SKILL.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    "apps/api/modules/users/service.py",
    "apps/web/modules/users/manifest.ts",
    "scripts/start.sh",
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """功能分支上, 還沒有任何改動 (實作還沒開始)。"""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    write(path, "README.md")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    git(path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(path, "switch", "-q", "-c", "feat/x")
    return path


def shell_decision(agent: str, repo: Path, command: str) -> str | None:
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    stdout = run(GUARD_COMMANDS, [agent], repo, payload)
    if not stdout.strip():
        return None
    output = json.loads(stdout)["hookSpecificOutput"]
    assert output["permissionDecisionReason"], "擋下時要說明理由與下一步"
    return str(output["permissionDecision"])


def approve(repo: Path, *paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, APPROVE, "protected", *paths],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )


@pytest.mark.parametrize("path", PROTECTED + LOCAL_ONLY)
@pytest.mark.parametrize("agent", AGENTS)
def test_editing_protected_files_needs_approval(agent: str, path: str, repo: Path) -> None:
    # repo 還沒開始實作: 防線檔案不像測試鎖, 任何時候都要同意。
    assert decision(agent, repo, path) == BLOCKED[agent], f"沒有攔下: {path}"


# 用 shell 改防線檔案不攔 (decisions.md 11): 寫法擋不完, 由審查時看 diff 的檔案清單補。
@pytest.mark.parametrize(
    "command",
    [
        "sed -i '' 's/x/y/' .github/workflows/ci.yml",
        "echo '{}' > .claude/settings.local.json",
        "chmod -x .githooks/commit-msg",
    ],
)
@pytest.mark.parametrize("agent", AGENTS)
def test_shell_writes_to_protected_files_are_not_guarded(
    agent: str, command: str, repo: Path
) -> None:
    assert shell_decision(agent, repo, command) is None, command


@pytest.mark.parametrize("path", ORDINARY)
@pytest.mark.parametrize("agent", AGENTS)
def test_ordinary_files_are_not_protected(agent: str, path: str, repo: Path) -> None:
    assert decision(agent, repo, path) is None, f"誤擋: {path}"


@pytest.mark.parametrize("agent", AGENTS)
def test_approved_protected_edit_is_allowed(agent: str, repo: Path) -> None:
    assert approve(repo, ".github/workflows/ci.yml").returncode == 0
    assert decision(agent, repo, ".github/workflows/ci.yml") is None
    assert decision(agent, repo, ".claude/settings.json") == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_protected_approval_lasts_for_the_branch_only(agent: str, repo: Path) -> None:
    assert approve(repo, ".github/workflows/ci.yml").returncode == 0
    write(repo, "README.md", "changed\n")
    git(repo, "commit", "-q", "-am", "next")
    assert decision(agent, repo, ".github/workflows/ci.yml") is None
    git(repo, "switch", "-q", "-c", "feat/next-task")
    assert decision(agent, repo, ".github/workflows/ci.yml") == BLOCKED[agent]


@pytest.mark.parametrize(
    "command",
    [
        f"echo '{{}}' > {APPROVAL_FILE}",
        f"touch {APPROVAL_FILE}",
        "./.agents/hooks/approve.py protected .github/workflows/ci.yml",
        "python .agents/hooks/approve.py protected .github/workflows/ci.yml",
    ],
)
@pytest.mark.parametrize("agent", AGENTS)
def test_guard_blocks_self_approval_of_protected_edits(
    agent: str, command: str, repo: Path
) -> None:
    assert shell_decision(agent, repo, command) == "deny", f"沒有擋下: {command}"


@pytest.mark.parametrize("agent", AGENTS)
def test_editing_protected_approval_file_directly_is_denied(agent: str, repo: Path) -> None:
    assert decision(agent, repo, APPROVAL_FILE) == "deny"


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_paths_exist(path: str) -> None:
    # 檔案改名或搬家時, 保護清單會安靜地指到不存在的路徑。
    assert (REPO_ROOT / path).exists(), f"{path} 不存在: 防線檔案的清單要跟著改"
