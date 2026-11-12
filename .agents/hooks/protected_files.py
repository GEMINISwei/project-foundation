"""防線檔案: hook、agent 設定、CI 與檢查的設定, 用改檔工具改之前要使用者同意 (不分實作前後)。

刪掉一個 CI 步驟或在 `.claude/settings.local.json` 設 `disableAllHooks`, 都不會有檢查變紅。
說明見 docs/foundation/hooks-and-skills.md〈防線檔案〉。
"""

from __future__ import annotations

from pathlib import Path

import approvals

# `.claude/` 包含不進版控的 settings.local.json; `.claude/skills` 是 symlink, 解析後不在這裡。
PROTECTED_DIRS = (
    ".agents/hooks/",
    ".claude/",
    ".codex/",
    ".githooks/",
    ".github/workflows/",
    ".github/scripts/",
    ".github/actions/",
)
# lint、型別、架構邊界、未使用匯出與覆蓋率門檻的設定, 以及檢查的入口。
PROTECTED_FILES = (
    "apps/api/pyproject.toml",
    "apps/web/package.json",
    "apps/web/eslint.config.mjs",
    "apps/web/.dependency-cruiser.cjs",
    "apps/web/knip.ts",
    "apps/web/tsconfig.json",
    "apps/web/vitest.config.ts",
    "tools/ruff.toml",
    "tools/commands/check.py",
    "tools/commands/e2e.py",
    "Makefile",
)


def is_protected(path: str) -> bool:
    return path.startswith(PROTECTED_DIRS) or path in PROTECTED_FILES


def pending_protected_edits(root: Path, files: list[str]) -> list[str]:
    protected = {path for path in files if is_protected(path)}
    return sorted(protected - approvals.approved(root, "protected"))


def verdict(pending: list[str]) -> tuple[str, str]:
    """兩家一樣: 擋下, 請 agent 說明後用一個指令申請全部要改的檔案, 使用者只確認一次。"""
    command = " ".join([*approvals.COMMAND, "protected", *pending, "[其他要改的防線檔案…]"])
    return (
        "deny",
        f"{', '.join(pending)} 是防線檔案（hook、agent 設定、CI 或檢查的設定），"
        "改動要先經過使用者同意。先在對話訊息裡一次列出這次要改的所有防線檔案，"
        "每個簡短說明原因、怎麼改、會不會讓哪一項檢查變寬鬆；最後才問一句是否全部同意"
        "（清單不要放進詢問視窗，項目一多使用者看不到）。"
        f"使用者同意後執行一次 `{command}`（會跳一次確認），"
        "之後在這個分支上改這些檔案不再詢問。",
    )
