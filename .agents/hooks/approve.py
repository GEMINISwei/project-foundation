#!/usr/bin/env python3
"""使用者同意後寫下放行: python3 .agents/hooks/approve.py <test|protected|branch> <路徑或分支>...

給 Codex 用 (它的 hook 不支援 ask), `.codex/rules/approve.rules` 讓它一定跳確認;
Claude 的 `permissions.ask` 也列了它。寫法固定, 換寫法呼叫會被 guard_commands.py 擋下。
"""

from __future__ import annotations

import sys
from pathlib import Path

import approvals
from protected_files import is_protected
from test_lock import is_test_file, relative, repo_root

CHECKS = {"test": is_test_file, "protected": is_protected}
USAGE = "用法: python3 .agents/hooks/approve.py <test|protected|branch> <路徑或分支>..."


def main() -> int:
    cwd = Path.cwd()
    root = repo_root(cwd)
    kind, values = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 2 else ("", [])
    if root is None or kind not in approvals.KINDS:
        print(USAGE, file=sys.stderr)
        return 2
    if kind in CHECKS:
        values = [relative(root, cwd, value) for value in values]
        others = [value for value in values if not CHECKS[kind](value)]
        if others:
            print(f"這些不是 {kind} 類別的檔案，不能放行: {others}", file=sys.stderr)
            return 2
    approvals.add(root, kind, values)
    expiry = "不隨 commit 失效" if kind == "branch" else "在目前這個分支上有效"
    print(f"已放行（{expiry}）: {', '.join(values)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
