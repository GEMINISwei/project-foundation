"""測試鎖定: 開始實作之後, agent 要改測試檔先經過使用者同意。

規則在 docs/foundation/testing.md〈改程式不改測試〉。只寫在文件時全靠 agent 自律, 對話一長、
上下文被壓縮後最容易破功, 而且測試被改成配合實作時, 所有檢查都是綠的。

是否「開始實作」從 git 推導, 不需要人標記: 分支相對 origin/main 的差異 (含還沒 commit 的)
有 apps/ 或 e2e/ 底下不是測試的檔案, 就算開始了。

兩家的同意方式不同: Claude 的 PreToolUse 可以回 ask, 畫面直接跳確認; Codex 只能回 deny,
所以由 agent 執行 `approve.py test` 申請, `.codex/rules/` 讓這個指令一定要使用者確認,
確認後寫下的放行只對列出的檔案、只在 HEAD 沒變之前有效。
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from support import REPO_ROOT
from test_hooks import CLAUDE_SETTINGS, CODEX_HOOKS, HOOKS_DIR, hook_calls

GIT = shutil.which("git") or "/usr/bin/git"
GUARD_TESTS = HOOKS_DIR / "guard_tests.py"
GUARD_COMMANDS = HOOKS_DIR / "guard_commands.py"
APPROVE = HOOKS_DIR / "approve.py"
APPROVE_COMMAND = "python3 .agents/hooks/approve.py test"
APPROVAL_FILE = ".git/agent-approvals"
CODEX_RULES = REPO_ROOT / ".codex" / "rules"
AGENTS = ("claude", "codex")
# 兩家一樣先擋下, 由 agent 說明後用 approve.py 一次申請全部要改的檔案。
BLOCKED = {"claude": "deny", "codex": "deny"}

SOURCE = "apps/api/modules/users/service.py"
TEST = "apps/api/tests/modules/users/test_service.py"
OTHER_TEST = "apps/web/tests/shared/api/payload.test.ts"
E2E_SUPPORT = "e2e/tests/support.ts"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [GIT, "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(repo: Path, path: str, text: str = "x\n") -> None:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """main 上有原始碼與測試, origin/main 指向它, 目前在功能分支上、還沒有任何改動。"""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    for name in (SOURCE, TEST, OTHER_TEST, E2E_SUPPORT, "README.md"):
        write(path, name)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    git(path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(path, "switch", "-q", "-c", "feat/x")
    return path


@pytest.fixture
def implementing(repo: Path) -> Path:
    write(repo, SOURCE, "changed\n")
    return repo


def run(script: Path, args: list[str], cwd: Path, payload: Any = None) -> str:
    return subprocess.run(
        [sys.executable, script, *args],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
    ).stdout


def edit_payload(agent: str, repo: Path, path: str, action: str = "Update") -> dict[str, Any]:
    if agent == "claude":
        tool, tool_input = (
            "Edit",
            {"file_path": str(repo / path), "old_string": "x", "new_string": "y"},
        )
    else:
        patch = f"*** Begin Patch\n*** {action} File: {path}\n@@\n-x\n+y\n*** End Patch\n"
        tool, tool_input = "apply_patch", {"command": patch}
    return {
        "hook_event_name": "PreToolUse",
        "cwd": str(repo),
        "tool_name": tool,
        "tool_input": tool_input,
    }


def decision(agent: str, repo: Path, path: str, action: str = "Update") -> str | None:
    stdout = run(GUARD_TESTS, [agent], repo, edit_payload(agent, repo, path, action))
    if not stdout.strip():
        return None
    output = json.loads(stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecisionReason"], "擋下時要說明理由與下一步"
    return str(output["permissionDecision"])


def approve(repo: Path, *paths: str, kind: str = "test") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, APPROVE, kind, *paths],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )


@pytest.mark.parametrize("agent", AGENTS)
def test_test_edits_are_allowed_before_implementation_starts(agent: str, repo: Path) -> None:
    write(repo, TEST, "new test\n")
    assert decision(agent, repo, TEST) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_doc_changes_do_not_start_implementation(agent: str, repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    assert decision(agent, repo, TEST) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_test_edits_need_approval_after_implementation_starts(
    agent: str, implementing: Path
) -> None:
    assert decision(agent, implementing, TEST) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_committed_implementation_also_locks_tests(agent: str, implementing: Path) -> None:
    git(implementing, "commit", "-q", "-am", "impl")
    assert decision(agent, implementing, TEST) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_e2e_support_files_count_as_tests(agent: str, implementing: Path) -> None:
    assert decision(agent, implementing, E2E_SUPPORT) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_adding_new_test_files_after_implementation_needs_approval(
    agent: str, implementing: Path
) -> None:
    new_test = "apps/api/tests/modules/users/test_new.py"
    assert decision(agent, implementing, new_test, action="Add") == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_source_edits_are_never_blocked(agent: str, implementing: Path) -> None:
    assert decision(agent, implementing, SOURCE) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_approved_test_edit_is_allowed(agent: str, implementing: Path) -> None:
    assert approve(implementing, TEST).returncode == 0
    assert decision(agent, implementing, TEST) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_approval_covers_only_listed_files(agent: str, implementing: Path) -> None:
    assert approve(implementing, TEST).returncode == 0
    assert decision(agent, implementing, OTHER_TEST) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_approval_lasts_for_the_branch_not_just_one_commit(agent: str, implementing: Path) -> None:
    # 一次說明、一次確認: 同一個任務裡每 commit 一次就再問一次, 只會讓人習慣性按同意。
    assert approve(implementing, TEST).returncode == 0
    git(implementing, "commit", "-q", "-am", "impl")
    assert decision(agent, implementing, TEST) is None


@pytest.mark.parametrize("agent", AGENTS)
def test_approval_does_not_carry_over_to_another_branch(agent: str, implementing: Path) -> None:
    assert approve(implementing, TEST).returncode == 0
    git(implementing, "commit", "-q", "-am", "impl")
    git(implementing, "switch", "-q", "-c", "feat/next-task")
    assert decision(agent, implementing, TEST) == BLOCKED[agent]


@pytest.mark.parametrize("agent", AGENTS)
def test_editing_approval_file_directly_is_denied(agent: str, repo: Path) -> None:
    assert decision(agent, repo, APPROVAL_FILE) == "deny"


@pytest.mark.parametrize(("kind", "path"), [("test", SOURCE), ("protected", "README.md")])
def test_approve_rejects_paths_outside_kind(kind: str, path: str, implementing: Path) -> None:
    result = approve(implementing, path, kind=kind)
    assert result.returncode != 0
    assert not (implementing / APPROVAL_FILE).exists()


@pytest.mark.parametrize(
    "command",
    [
        f"echo '{{}}' > {APPROVAL_FILE}",
        f"touch {APPROVAL_FILE}",
        f"./.agents/hooks/approve.py test {TEST}",
        f"python .agents/hooks/approve.py test {TEST}",
        f"cd apps && python3 ../.agents/hooks/approve.py test {TEST}",
        "python3 -c \"import runpy; runpy.run_path('.agents/hooks/approve.py')\"",
        f"python3 -c \"open('{APPROVAL_FILE}', 'w').write('{{}}')\"",
        f"node -e \"require('fs').writeFileSync('{APPROVAL_FILE}', '{{}}')\"",
    ],
)
@pytest.mark.parametrize("agent", AGENTS)
def test_guard_blocks_self_approval_outside_the_prompted_command(
    agent: str, command: str, repo: Path
) -> None:
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    output = run(GUARD_COMMANDS, [agent], repo, payload)
    assert output.strip(), f"沒有擋下: {command}"
    assert json.loads(output)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("agent", AGENTS)
def test_guard_allows_the_prompted_approval_command(agent: str, repo: Path) -> None:
    command = f"{APPROVE_COMMAND} {TEST}"
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    assert not run(GUARD_COMMANDS, [agent], repo, payload).strip()


@pytest.mark.parametrize(
    "command",
    [
        "chmod +x .agents/hooks/approve.py",
        "cat .agents/hooks/approve.py",
        f"cat {APPROVAL_FILE}",
        f"ls {APPROVAL_FILE}",
        f"cat {APPROVAL_FILE} 2>/dev/null",
        f"jq . {APPROVAL_FILE}",
        f"python3 -m json.tool {APPROVAL_FILE}",
    ],
)
@pytest.mark.parametrize("agent", AGENTS)
def test_guard_allows_commands_that_only_mention_the_approval_files(
    agent: str, command: str, repo: Path
) -> None:
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}}
    assert not run(GUARD_COMMANDS, [agent], repo, payload).strip(), f"誤擋: {command}"


def test_test_guard_is_configured_for_edit_tools() -> None:
    for config in (CLAUDE_SETTINGS, CODEX_HOOKS):
        calls = hook_calls(json.loads(config.read_text(encoding="utf-8")))
        matchers = [
            matcher
            for event, matcher, script, _ in calls
            if event == "PreToolUse" and script.endswith("/guard_tests.py")
        ]
        assert matchers, f"{config.name} 沒有掛 guard_tests.py"
        assert all({"Edit", "Write"} <= set(matcher.split("|")) for matcher in matchers)


def test_codex_rules_prompt_before_approving() -> None:
    rules = "\n".join(path.read_text(encoding="utf-8") for path in CODEX_RULES.glob("*.rules"))
    pattern = re.compile(
        r'prefix_rule\(\s*pattern\s*=\s*\[\s*"python3"\s*,\s*"\.agents/hooks/approve\.py"'
        r'\s*\][^)]*decision\s*=\s*"prompt"',
        flags=re.DOTALL,
    )
    assert pattern.search(rules), ".codex/rules/ 要讓 approve.py 一定經過使用者確認"
    names = sorted(path.name for path in CODEX_RULES.glob("*.rules"))
    assert names == ["approve.rules", "publish-release.rules"], f"Codex rule 只留兩條: {names}"


def test_claude_asks_before_approving() -> None:
    settings = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    ask = settings.get("permissions", {}).get("ask", [])
    assert "Bash(python3 .agents/hooks/approve.py:*)" in ask


# 用 shell 改測試檔不攔 (decisions.md 11): 寫法擋不完, 交給 agent 自律與審查時看 diff 補。
SHELL_WRITES = [
    f"sed -i '' 's/x/y/' {TEST}",
    f"echo y > {TEST}",
    f"rm {TEST}",
    f"git checkout main -- {TEST}",
    f"python3 -c \"open('{TEST}', 'w').write('')\"",
]


@pytest.mark.parametrize("command", SHELL_WRITES)
@pytest.mark.parametrize("agent", AGENTS)
def test_shell_writes_to_tests_are_not_guarded(
    agent: str, command: str, implementing: Path
) -> None:
    payload = {"cwd": str(implementing), "tool_name": "Bash", "tool_input": {"command": command}}
    assert not run(GUARD_COMMANDS, [agent], implementing, payload).strip(), command
