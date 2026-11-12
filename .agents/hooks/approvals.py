"""使用者的放行紀錄: `.git/agent-approvals`, 只由 approve.py 寫入 (Codex rule 讓它一定跳確認)。

- test、protected: 放行列出的檔案, 在寫下時的那個分支上有效 (換分支就失效): 一次說明、
  一次確認, 之後在同一個任務裡改這些檔案不再詢問。
- branch: 有開著的 PR 時插隊的分支名稱, 不隨 commit 失效。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

NAME = "agent-approvals"
COMMAND = ["python3", ".agents/hooks/approve.py"]
KINDS = ("test", "protected", "branch")


def git(cwd: Path, *args: str) -> str | None:
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def path(root: Path) -> Path:
    return (root / (git(root, "rev-parse", "--git-path", NAME) or "")).resolve()


def load(root: Path) -> dict[str, object]:
    try:
        data = json.loads(path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def scope(root: Path) -> str | None:
    """放行的有效範圍: 目前的分支 (沒有分支時是 HEAD 的 commit)。"""
    return git(root, "symbolic-ref", "--quiet", "--short", "HEAD") or git(root, "rev-parse", "HEAD")


def approved(root: Path, kind: str) -> set[str]:
    data = load(root)
    if kind != "branch" and data.get("scope") != scope(root):
        return set()
    values = data.get(kind, [])
    if not isinstance(values, list):
        return set()
    return {value for value in values if isinstance(value, str)}


def add(root: Path, kind: str, values: list[str]) -> None:
    data = {name: sorted(approved(root, name)) for name in KINDS}
    data[kind] = sorted(set(data[kind]) | set(values))
    path(root).write_text(json.dumps({"scope": scope(root), **data}), encoding="utf-8")
