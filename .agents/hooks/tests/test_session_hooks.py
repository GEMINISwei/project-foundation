"""session 層級的 hook: 開工時提示現況 (SessionStart)。

- 沒有 Stop hook: 完整的檢查只在 CI 跑, agent push 之後照 watch-pr 等結果, 不在本機收尾前要求。
- SessionStart: 開新 session、恢復或壓縮後, 告訴 agent 目前的分支、開著的 PR、測試鎖的狀態,
  它才不會在等合併時順手開新分支, 或忘了實作已經開始。

兩家的格式相同 (SessionStart 回 additionalContext), 所以不需要分家處理。
另外用 PATH 上的 python3 (hook 實際用的那一個) 實際跑一次每個設定的 hook: 其他測試用的是
api 的虛擬環境, 抓不到使用者機器上 python3 太舊、腳本一跑就壞的情況。
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import REPO_ROOT
from test_hooks import CLAUDE_SETTINGS, CODEX_HOOKS, HOOKS_DIR, hook_calls
from test_test_guard import AGENTS, BLOCKED, decision, git, write

SESSION_CONTEXT = HOOKS_DIR / "session_context.py"
PYTHON3 = shutil.which("python3", path="/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin")

SOURCE = "apps/api/modules/users/service.py"
TEST = "apps/api/tests/modules/users/test_service.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """main 上有原始碼與測試, origin/main 指向它, 目前在功能分支上、還沒有任何改動。"""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    for name in (SOURCE, TEST, "README.md"):
        write(path, name)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    git(path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(path, "switch", "-q", "-c", "feat/x")
    return path


def run_hook(
    script: Path,
    agent: str,
    repo: Path,
    payload: dict[str, Any],
    env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    payload = {"cwd": str(repo), **payload}
    result = subprocess.run(  # 執行受測的 hook
        [PYTHON3 or "python3", script, agent],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=repo,
        env=env,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def fake_gh(tmp_path: Path, prs: list[dict[str, Any]] | None) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "gh"
    output = f"echo '{json.dumps(prs)}'" if prs is not None else "exit 1"
    script.write_text(f"#!/bin/sh\n{output}\n", encoding="utf-8")
    script.chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin"}


def session_context(agent: str, repo: Path, env: dict[str, str]) -> str:
    payload = {"hook_event_name": "SessionStart", "source": "startup"}
    output = run_hook(SESSION_CONTEXT, agent, repo, payload, env)
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "SessionStart"
    return str(specific["additionalContext"])


@pytest.mark.parametrize("agent", AGENTS)
def test_session_start_reports_branch_prs_and_test_lock(
    agent: str, repo: Path, tmp_path: Path
) -> None:
    prs = [{"number": 30, "headRefName": "feat/x", "isDraft": True}]
    write(repo, SOURCE, "changed\n")
    context = session_context(agent, repo, fake_gh(tmp_path, prs))
    assert "feat/x" in context
    assert "#30" in context
    assert "實作已經開始" in context


@pytest.mark.parametrize("agent", AGENTS)
def test_session_start_works_without_gh(agent: str, repo: Path, tmp_path: Path) -> None:
    context = session_context(agent, repo, fake_gh(tmp_path, None))
    assert "feat/x" in context
    assert "實作還沒開始" in context


def test_session_hooks_are_configured() -> None:
    for config in (CLAUDE_SETTINGS, CODEX_HOOKS):
        calls = {call[:3] for call in hook_calls(json.loads(config.read_text(encoding="utf-8")))}
        # 收尾前不要求本機跑完整的檢查: 完整的檢查只在 CI 跑, 結果由 watch-pr 等。
        assert not any(call[0] == "Stop" for call in calls), config.name
        session = (
            "SessionStart",
            "startup|resume|clear|compact",
            ".agents/hooks/session_context.py",
        )
        assert session in calls, config.name


def sample_payload(event: str, matcher: str) -> dict[str, Any]:
    if event == "PreToolUse" and "Bash" in matcher.split("|"):
        return {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    if event == "PreToolUse":
        return {"tool_name": "Edit", "tool_input": {"file_path": "README.md"}}
    return {"source": "startup"}


@pytest.mark.skipif(PYTHON3 is None, reason="PATH 上沒有 python3 (init 會擋下)")
@pytest.mark.parametrize("config", [CLAUDE_SETTINGS, CODEX_HOOKS], ids=lambda path: path.name)
def test_configured_hooks_run_with_python3_on_path(config: Path, repo: Path) -> None:
    for event, matcher, script, agent in hook_calls(json.loads(config.read_text("utf-8"))):
        payload = {"hook_event_name": event, **sample_payload(event, matcher)}
        result = subprocess.run(  # 用 hook 實際的直譯器跑設定裡的腳本
            [PYTHON3 or "python3", REPO_ROOT / script, agent],
            input=json.dumps({"cwd": str(repo), **payload}),
            capture_output=True,
            text=True,
            cwd=repo,
            env={"PATH": "/usr/bin:/bin"},
            check=False,
        )
        assert result.returncode == 0, f"{script} ({event}) 跑不起來: {result.stderr}"
        if result.stdout.strip():
            json.loads(result.stdout)


@pytest.mark.parametrize(
    "path", [".agents/hooks/x.py", ".github/scripts/x.py", "tools/commands/check.py"]
)
@pytest.mark.parametrize("agent", AGENTS)
def test_hook_and_script_changes_start_implementation(agent: str, path: str, repo: Path) -> None:
    # 它們的測試也放在 apps/api/tests/, 改了就該鎖住測試。
    write(repo, path, "changed\n")
    assert decision(agent, repo, TEST) == BLOCKED[agent]
