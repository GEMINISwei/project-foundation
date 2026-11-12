"""一次一個 PR: 使用者有沒有開著的 PR。規則見 docs/foundation/workflow.md〈一次一個 PR〉。"""

from __future__ import annotations

import json
import subprocess

# 只算使用者自己開的: Dependabot 的安全更新不是 agent 進行中的工作。
GH_OPEN_PRS = ("gh", "pr", "list", "--author", "@me", "--state", "open", "--json", "headRefName")


def open_prs(cwd: str) -> list[str]:
    """開著的 PR 的分支名稱。查不到 (沒網路、沒登入) 當作沒有: 這是流程規則, 不是安全邊界。"""
    try:
        result = subprocess.run(  # noqa: S603
            [*GH_OPEN_PRS],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        prs = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    return [str(pr.get("headRefName", "")) for pr in prs if isinstance(pr, dict)]
