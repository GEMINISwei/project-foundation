#!/usr/bin/env python3
"""改檔 hook: Claude 與 Codex 的 PreToolUse hook, 這兩種檔案改動前要使用者同意。

- 測試檔: 開始實作之後改掉既有的程式碼 (test_lock.py); 只加不改的不擋, 只改註解、docstring
  與空行的也不擋 (拿掉這些再比對, 判斷沿用 .github/scripts/check-pr-changes.py)
- 防線檔案 (hook、agent 設定、CI、檢查的設定): 任何時候 (protected_files.py)

用法 (由 .claude/settings.json 與 .codex/hooks.json 呼叫): guard_tests.py <claude|codex>

兩家的行為相同: 擋下這次改動, 請 agent 向使用者一次說明所有要改的檔案, 再用一個指令
(approve.py) 申請; 那個指令兩家都設成一定跳確認 (Claude 的 permissions.ask、Codex 的 rules)。
使用者確認一次之後, 在這個分支上改那些檔案不再詢問。參數 (claude|codex) 只為了與其他 hook 的
呼叫方式一致, 這裡用不到。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import approvals
import protected_files
from test_lock import is_test_file, pending_test_edits, relative, repo_root, verdict

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Codex 的 apply_patch 把整段 patch 放在 command 裡, 檔名在這幾種標頭行。
PATCH_FILE = re.compile(r"^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$", re.M)

# 下面回傳的 dict: 要改的檔案 → 這次新增的行; 改到或刪掉既有的行、判斷不出來時是 None。


def added_lines(before: str, after: str) -> list[str] | None:
    """after 比 before 多出來的行; before 的行沒有照原本的順序全部留著時是 None。"""
    old = before.splitlines()
    kept = 0
    added = []
    for line in after.splitlines():
        if kept < len(old) and line == old[kept]:
            kept += 1
        else:
            added.append(line)
    return added if kept == len(old) else None


def comment_rules() -> Any:
    script = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "check-pr-changes.py"
    spec = importlib.util.spec_from_file_location("check_pr_changes", script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def added_code(path: str, before: str, after: str) -> list[str] | None:
    rules = comment_rules()
    if rules is None:
        return added_lines(before, after)
    old = "\n".join(rules.code_lines(path, before))
    new = "\n".join(rules.code_lines(path, after))
    return added_lines(old, new)


def after_patch(text: str, body: list[str]) -> str | None:
    lines = text.splitlines()
    hunks: list[list[str]] = [[]]
    for line in body:
        if line.startswith("@@"):
            hunks.append([])
        elif not line.startswith("***"):
            hunks[-1].append(line)
    for hunk in (item for item in hunks if item):
        old = [line[1:] for line in hunk if not line.startswith("+")]
        new = [line[1:] for line in hunk if not line.startswith("-")]
        found = next(
            (index for index in range(len(lines) + 1) if lines[index : index + len(old)] == old),
            None,
        )
        if found is None:
            return None
        lines[found : found + len(old)] = new
    return "\n".join(lines) + "\n"


def after_replacements(text: str, edits: object) -> str | None:
    if not isinstance(edits, list):
        return None
    for edit in edits:
        old = edit.get("old_string") if isinstance(edit, dict) else None
        new = edit.get("new_string") if isinstance(edit, dict) else None
        if not isinstance(old, str) or not isinstance(new, str) or old not in text:
            return None
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    return text


def tool_edits(
    tool: object, tool_input: dict[str, object], cwd: Path
) -> dict[str, list[str] | None]:
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(path, str):
        return {}
    target = cwd / path
    try:
        before = target.read_text(encoding="utf-8") if target.exists() else ""
    except (OSError, ValueError):
        return {path: None}
    after: object = None
    if tool == "Write":
        after = tool_input.get("content")
    elif tool == "Edit":
        after = after_replacements(before, [tool_input])
    elif tool == "MultiEdit":
        after = after_replacements(before, tool_input.get("edits"))
    return {path: added_code(path, before, after) if isinstance(after, str) else None}


def patch_edits(patch: str, cwd: Path) -> dict[str, list[str] | None]:
    edits: dict[str, list[str] | None] = {}
    sections = PATCH_FILE.split(patch)[1:]
    for kind, name, body in zip(sections[0::3], sections[1::3], sections[2::3]):
        path = name.strip()
        lines = body.splitlines()
        earlier = edits.get(path, [])
        if kind == "Add File" and not (cwd / path).exists() and earlier is not None:
            edits[path] = earlier + [line[1:] for line in lines if line.startswith("+")]
        elif kind == "Update File" and path not in edits:
            edits[path] = updated(cwd / path, path, lines[1:] if lines[:1] == [""] else lines)
        else:
            edits[path] = None
    return edits


def updated(target: Path, path: str, body: list[str]) -> list[str] | None:
    try:
        before = target.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    after = after_patch(before, body)
    return added_code(path, before, after) if after is not None else None


def edited_files(payload: dict[str, object], cwd: Path) -> dict[str, list[str] | None]:
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}
    if tool in EDIT_TOOLS:
        return tool_edits(tool, tool_input, cwd)
    if tool == "apply_patch" and isinstance(tool_input.get("command"), str):
        return patch_edits(tool_input["command"], cwd)
    return {}


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
    edits = edited_files(payload, cwd)
    if root is None or not edits:
        return 0
    files = {relative(root, cwd, path): added for path, added in edits.items()}
    if any(approvals.NAME in path for path in files):
        respond("deny", "放行檔只能由使用者確認過的申請指令寫入，不要直接修改。")
        return 0
    protected = protected_files.pending_protected_edits(root, list(files))
    if protected:
        respond(*protected_files.verdict(protected))
        return 0
    tests = {path: added for path, added in files.items() if is_test_file(path)}
    pending = pending_test_edits(root, tests)
    if pending:
        respond(*verdict(pending))
    return 0


if __name__ == "__main__":
    sys.exit(main())
