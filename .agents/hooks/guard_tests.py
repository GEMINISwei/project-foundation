#!/usr/bin/env python3
"""改檔 hook: Claude 與 Codex 的 PreToolUse hook, 這兩種檔案改動前要使用者同意。

- 測試檔: 開始實作之後 (test_lock.py)
- 防線檔案 (hook、agent 設定、CI、檢查的設定): 任何時候 (protected_files.py)

用法 (由 .claude/settings.json 與 .codex/hooks.json 呼叫): guard_tests.py <claude|codex>

兩家的行為相同: 擋下這次改動, 請 agent 向使用者一次說明所有要改的檔案, 再用一個指令
(approve.py) 申請; 那個指令兩家都設成一定跳確認 (Claude 的 permissions.ask、Codex 的 rules)。
使用者確認一次之後, 在這個分支上改那些檔案不再詢問。參數 (claude|codex) 只為了與其他 hook 的
呼叫方式一致, 這裡用不到。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import approvals
import protected_files
from test_lock import is_test_file, pending_test_edits, relative, repo_root, verdict

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Codex 的 apply_patch 把整段 patch 放在 command 裡, 檔名在這幾種標頭行。
PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.M)


def edited_paths(payload: dict[str, object]) -> list[str]:
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    if tool in EDIT_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        return [path] if isinstance(path, str) else []
    if tool == "apply_patch" and isinstance(tool_input.get("command"), str):
        return [name.strip() for name in PATCH_FILE.findall(tool_input["command"])]
    return []


def respond(decision: str, reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    json.dump(output, sys.stdout, ensure_ascii=False)


def main() -> int:
    payload = json.load(sys.stdin)
    cwd = Path(payload.get("cwd") or ".")
    root = repo_root(cwd)
    paths = edited_paths(payload)
    if root is None or not paths:
        return 0
    files = [relative(root, cwd, path) for path in paths]
    if any(approvals.NAME in path for path in files):
        respond("deny", "放行檔只能由使用者確認過的申請指令寫入，不要直接修改。")
        return 0
    protected = protected_files.pending_protected_edits(root, files)
    if protected:
        respond(*protected_files.verdict(protected))
        return 0
    pending = pending_test_edits(root, [path for path in files if is_test_file(path)])
    if pending:
        respond(*verdict(pending))
    return 0


if __name__ == "__main__":
    sys.exit(main())
