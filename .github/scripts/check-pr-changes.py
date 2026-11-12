#!/usr/bin/env python3
"""PR 的改動檢查: BASE_SHA=… HEAD_SHA=… .github/scripts/check-pr-changes.py

pr.yml 呼叫, 本機也能跑。只檢查一件事: 這個 PR 新增的抑制註解同一行要寫理由
(docs/foundation/development.md〈抑制註解〉)。只看這個 PR 新增的行。

實作後改測試檔、動到防線檔案, 不要求在 PR 描述裡再寫一次: 改的當下 hook 已經請使用者確認,
審查時 diff 的檔案清單也看得到 (docs/foundation/hooks-and-skills.md)。
要能在 Python 3.9 上跑 (macOS 內建)。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs")
# 呼叫子行程的警告: hook 與測試用固定參數呼叫 git、gh 是常態, 每次寫理由只是噪音。
EXEMPT_NOQA = {"S603", "S607"}

NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*))?(?P<rest>.*)$")
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<rest>.*)$")
ESLINT = re.compile(r"(?://|/\*)\s*eslint-disable[\w-]*(?P<rest>.*)$")
TS_DIRECTIVE = re.compile(r"//\s*@ts-(?:expect-error|ignore)(?P<rest>.*)$")
PYTEST_SKIP = re.compile(r"pytest\.(?:mark\.skip(?:if)?|skip)\b(?P<rest>.*)$")
JS_SKIP = re.compile(r"\b(?:it|test|describe)\.skip\((?P<rest>.*)$")


def git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def added_lines(base: str, head: str) -> list[tuple[str, str]]:
    """(檔案, 新增的那一行), 只看程式碼。"""
    diff = git("diff", "-U0", "--no-color", f"{base}...{head}")
    result = []
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and path.endswith(CODE_SUFFIXES):
            result.append((path, line[1:]))
    return result


def has_comment(rest: str, marker: str) -> bool:
    """rest 裡在 marker 之後還有文字 (marker 為空時, rest 本身有文字)。"""
    if not marker:
        return bool(rest.strip(" */"))
    _, found, reason = rest.partition(marker)
    return bool(found) and bool(reason.strip(" */"))


def missing_reason(line: str) -> str | None:
    """這一行的抑制註解沒寫理由時, 回傳它是哪一種。"""
    match = NOQA.search(line)
    if match:
        codes = {code.strip() for code in (match.group("codes") or "").split(",") if code.strip()}
        if codes and codes <= EXEMPT_NOQA:
            return None
        return None if has_comment(match.group("rest"), "#") else "noqa"
    match = TYPE_IGNORE.search(line)
    if match:
        return None if has_comment(match.group("rest"), "#") else "type: ignore"
    match = ESLINT.search(line)
    if match:
        return None if has_comment(match.group("rest"), "--") else "eslint-disable（用 `-- 理由`）"
    match = TS_DIRECTIVE.search(line)
    if match:
        return None if has_comment(match.group("rest"), "") else "@ts-expect-error"
    match = PYTEST_SKIP.search(line)
    if match:
        rest = match.group("rest")
        has_reason = "reason=" in rest or re.match(r"\(\s*['\"]", rest) is not None
        return None if has_reason else "pytest skip（要帶 reason）"
    match = JS_SKIP.search(line)
    if match:
        return None if has_comment(match.group("rest"), "//") else "skip（同一行用 `//` 寫理由）"
    return None


def main() -> int:
    base = os.environ["BASE_SHA"]
    head = os.environ["HEAD_SHA"]
    errors = []
    for path, line in added_lines(base, head):
        kind = missing_reason(line)
        if kind:
            errors.append(f"{path}: 新增的 {kind} 要在同一行寫理由：{line.strip()}")

    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
