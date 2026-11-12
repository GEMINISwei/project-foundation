#!/usr/bin/env python3
"""SessionStart hook: 開工時告訴 agent 目前的分支、開著的 PR 與測試鎖的狀態。

用法 (由 .claude/settings.json 與 .codex/hooks.json 呼叫): session_context.py <claude|codex>

兩家的格式相同: `hookSpecificOutput.additionalContext` 會加進 agent 的上下文。開新 session、恢復或
壓縮上下文之後, agent 不記得進行到哪, 容易在等合併時順手開新分支, 或忘了實作已經開始。
查不到 PR (沒網路、gh 沒登入) 時省略那一行, 不影響開工。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import approvals
from test_lock import git, implementation_started, repo_root


def open_prs(cwd: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            [  # noqa: S607
                "gh",
                "pr",
                "list",
                "--author",
                "@me",
                "--state",
                "open",
                "--json",
                "number,headRefName,isDraft",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        prs = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if not isinstance(prs, list):
        return None
    return [
        f"#{pr.get('number')} {pr.get('headRefName')}{'（Draft）' if pr.get('isDraft') else ''}"
        for pr in prs
        if isinstance(pr, dict)
    ]


def context(root: Path) -> str:
    branch = git(root, "symbolic-ref", "--short", "-q", "HEAD") or "（detached HEAD）"
    lines = [f"這個 repo 的現況（{root.name}）：", f"- 目前分支：{branch}"]
    prs = open_prs(root)
    if prs is not None:
        if prs:
            lines.append(
                f"- 你開著的 PR：{'、'.join(prs)}。一次只有一個進行中的 PR，"
                "合併前不要開新分支（docs/foundation/workflow.md〈一次一個 PR〉）"
            )
        else:
            lines.append("- 沒有開著的 PR")
    if implementation_started(root):
        approved = sorted(approvals.approved(root, "test"))
        note = f"，已放行：{'、'.join(approved)}" if approved else ""
        lines.append(f"- 實作已經開始：改測試檔要先經過使用者同意{note}")
    else:
        lines.append("- 實作還沒開始（測試檔還沒鎖定）")
    branches = sorted(approvals.approved(root, "branch"))
    if branches:
        lines.append(f"- 使用者同意插隊的分支：{'、'.join(branches)}")
    return "\n".join(lines)


def main() -> int:
    payload = json.load(sys.stdin)
    root = repo_root(Path(payload.get("cwd") or "."))
    if root is None:
        return 0
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context(root),
        }
    }
    json.dump(output, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
