#!/usr/bin/env python3
"""PR 的改動檢查: BASE_SHA=… HEAD_SHA=… .github/scripts/check-pr-changes.py

pr.yml 呼叫, 本機也能跑。只看這個 PR 新增的行。

擋下新增的抑制註解同一行沒寫理由 (docs/foundation/development.md〈抑制註解〉)。
有 GITHUB_STEP_SUMMARY 時把審查要看的東西寫成表格: 沒過的項目、新增的抑制註解、
改掉既有內容的測試檔、動到的防線檔案。沒有要看的項目時只有一行。
code_lines 拿掉註解與 docstring, 測試鎖 (.agents/hooks/guard_tests.py) 也用它比對;
測試檔與防線檔案的定義跟 hook 共用 (.agents/hooks/)。
要能在 Python 3.9 上跑 (macOS 內建)。
"""

from __future__ import annotations

import ast
import importlib
import io
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any, NamedTuple

CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs")
# 呼叫子行程的警告: hook 與測試用固定參數呼叫 git、gh 是常態, 每次寫理由只是噪音。
EXEMPT_NOQA = {"S603", "S607"}

NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*))?(?P<rest>.*)$")
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<rest>.*)$")
ESLINT = re.compile(r"(?://|/\*)\s*eslint-disable[\w-]*(?P<rest>.*)$")
TS_DIRECTIVE = re.compile(r"//\s*@ts-(?:expect-error|ignore)(?P<rest>.*)$")
PYTEST_SKIP = re.compile(r"pytest\.(?:mark\.skip(?:if)?|skip)\b(?P<rest>.*)$")
JS_SKIP = re.compile(r"\b(?:it|test|describe)\.skip\((?P<rest>.*)$")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")

REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")
REGEX_AFTER_WORDS = {
    *("return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void"),
    *("throw", "instanceof", "yield", "await"),
}


class Docstring(NamedTuple):
    start: int
    end: int
    kind: str
    text: str


def hook_module(name: str) -> Any:
    hooks = Path(__file__).resolve().parents[2] / ".agents" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    return importlib.import_module(name)


def git(*args: str) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def added_lines(base: str, head: str) -> dict[str, dict[int, str]]:
    """{檔案: {head 的行號: 新增的那一行}}。"""
    diff = git("diff", "-U0", "--no-color", "--no-renames", f"{base}...{head}")
    result: dict[str, dict[int, str]] = {}
    path, number = "", 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@"):
            hunk = HUNK.match(line)
            number = int(hunk.group(1)) if hunk else 0
        elif line.startswith("+") and path:
            result.setdefault(path, {})[number] = line[1:]
            number += 1
    return result


def has_comment(rest: str, marker: str) -> bool:
    """rest 裡在 marker 之後還有文字 (marker 為空時, rest 本身有文字)。"""
    if not marker:
        return bool(rest.strip(" */"))
    _, found, reason = rest.partition(marker)
    return bool(found) and bool(reason.strip(" */"))


def suppression(line: str) -> tuple[str, bool] | None:
    """(種類, 有沒有理由); 不是抑制註解、或是不必寫理由的 noqa 時回傳 None。"""
    match = NOQA.search(line)
    if match:
        codes = {code.strip() for code in (match.group("codes") or "").split(",") if code.strip()}
        if codes and codes <= EXEMPT_NOQA:
            return None
        return "noqa", has_comment(match.group("rest"), "#")
    match = TYPE_IGNORE.search(line)
    if match:
        return "type: ignore", has_comment(match.group("rest"), "#")
    match = ESLINT.search(line)
    if match:
        return "eslint-disable（用 `-- 理由`）", has_comment(match.group("rest"), "--")
    match = TS_DIRECTIVE.search(line)
    if match:
        return "@ts-expect-error", has_comment(match.group("rest"), "")
    match = PYTEST_SKIP.search(line)
    if match:
        rest = match.group("rest")
        return "pytest skip（要帶 reason）", "reason=" in rest or bool(
            re.match(r"\(\s*['\"]", rest)
        )
    match = JS_SKIP.search(line)
    if match:
        return "skip（同一行用 `//` 寫理由）", has_comment(match.group("rest"), "//")
    return None


class Scanner:
    """找出 TypeScript 的註解, 跳過字串、樣板字串與正規表示式。

    pr job 不安裝 Node 的相依, 用不了正式的 parser; 正規表示式與除號靠前一個記號判斷。
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0
        self.line = 1
        self.previous = ""
        self.word = ""
        self.templates: list[int] = []
        self.comments: list[tuple[int, str, bool, bool]] = []
        self.spans: list[tuple[int, int]] = []

    def advance(self, end: int) -> None:
        self.line += self.source.count("\n", self.index, end)
        self.index = end

    def full_line(self) -> bool:
        start = self.source.rfind("\n", 0, self.index) + 1
        return not self.source[start : self.index].strip()

    def comment(self, block: bool) -> None:
        if block:
            close = self.source.find("*/", self.index + 2)
            end = len(self.source) if close < 0 else close + 2
            body = self.source[self.index + 2 : max(self.index + 2, end - 2)]
        else:
            close = self.source.find("\n", self.index)
            end = len(self.source) if close < 0 else close
            body = self.source[self.index + 2 : end]
        self.comments.append((self.line, body, self.full_line(), block))
        self.spans.append((self.index, end))
        self.advance(end)

    def quoted(self, quote: str) -> None:
        position = self.index + 1
        while position < len(self.source) and self.source[position] not in (quote, "\n"):
            position += 2 if self.source[position] == "\\" else 1
        self.advance(position + 1)

    def template(self) -> None:
        position = self.index
        while position < len(self.source):
            char = self.source[position]
            if char == "\\":
                position += 2
            elif char == "`":
                self.advance(position + 1)
                return
            elif self.source.startswith("${", position):
                self.templates.append(0)
                self.advance(position + 2)
                return
            else:
                position += 1
        self.advance(position)

    def regex(self) -> None:
        position, in_class = self.index + 1, False
        while position < len(self.source) and self.source[position] != "\n":
            char = self.source[position]
            if char == "\\":
                position += 1
            elif char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                break
            position += 1
        self.advance(position + 1)

    def regex_allowed(self) -> bool:
        return self.previous in ("", *REGEX_BEFORE, "}") or self.word in REGEX_AFTER_WORDS

    def brace(self, char: str) -> bool:
        """`${…}` 結束時回到樣板字串, 回傳 True。"""
        if not self.templates:
            return False
        if char == "{":
            self.templates[-1] += 1
            return False
        if self.templates[-1] == 0:
            self.templates.pop()
            self.index += 1
            self.template()
            return True
        self.templates[-1] -= 1
        return False

    def token(self) -> None:
        char, pair = self.source[self.index], self.source[self.index : self.index + 2]
        if pair in ("//", "/*"):
            self.comment(block=pair == "/*")
            return
        if char in "'\"":
            self.quoted(char)
        elif char == "`":
            self.index += 1
            self.template()
        elif char == "/" and self.regex_allowed():
            self.regex()
        elif char in "{}" and self.brace(char):
            pass
        else:
            word = re.match(r"[\w$]+", self.source[self.index :])
            end = self.index + (len(word.group(0)) if word else 1)
            self.word = word.group(0) if word else ""
            self.previous = "a" if word else char
            self.advance(end)
            return
        self.previous, self.word = "a", ""

    def scan(self) -> list[tuple[int, str, bool, bool]]:
        while self.index < len(self.source):
            if self.source[self.index].isspace():
                self.advance(self.index + 1)
            else:
                self.token()
        return self.comments


def literal(text: str) -> str:
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    return value if isinstance(value, str) else text


def nesting(token: tokenize.TokenInfo) -> int:
    if token.type != tokenize.OP:
        return 0
    return 1 if token.string in "([{" else -1 if token.string in ")]}" else 0


def python_docstrings(source: str) -> list[Docstring]:
    result: list[Docstring] = []
    expect: str | None = "module"
    pending: str | None = None
    depth, ready = 0, False
    skipped = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.INDENT, tokenize.DEDENT)
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in skipped:
                continue
            if token.type == tokenize.NEWLINE:
                if ready:
                    expect, pending, ready = pending, None, False
                continue
            if expect and token.type == tokenize.STRING:
                text = literal(token.string)
                result.append(Docstring(token.start[0], token.end[0], expect, text))
            expect = None
            depth += nesting(token)
            if token.type == tokenize.NAME and token.string in ("def", "class") and not depth:
                pending = "class" if token.string == "class" else "function"
            ready = ready or (token.string == ":" and pending is not None and not depth)
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return result
    return result


def python_code(source: str) -> str:
    lines = source.splitlines()
    comments: list[tuple[int, int]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                comments.append(token.start)
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return source
    for row, column in comments:
        lines[row - 1] = lines[row - 1][:column]
    for doc in python_docstrings(source):
        for row in range(doc.start, doc.end + 1):
            lines[row - 1] = ""
    return "\n".join(lines)


def typescript_code(source: str) -> str:
    scanner = Scanner(source)
    scanner.scan()
    parts, position = [], 0
    for start, end in scanner.spans:
        parts.append(source[position:start])
        parts.append("\n" * source.count("\n", start, end))
        position = end
    return "".join([*parts, source[position:]])


def code_lines(path: str, source: str) -> list[str]:
    if path.endswith(".py"):
        source = python_code(source)
    elif path.endswith((".ts", ".tsx")):
        source = typescript_code(source)
    return [line.rstrip() for line in source.splitlines() if line.strip()]


class Review:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.suppressions: list[tuple[str, str]] = []
        self.tests: list[tuple[str, str]] = []
        self.protected: list[str] = []


def review_suppressions(added: dict[str, dict[int, str]], review: Review) -> None:
    for path, lines in added.items():
        if not path.endswith(CODE_SUFFIXES):
            continue
        for number, line in lines.items():
            found = suppression(line)
            if not found:
                continue
            kind, has_reason = found
            where = f"{path}:{number}"
            review.suppressions.append((where, line.strip()))
            if not has_reason:
                review.errors.append((where, f"新增的 {kind} 要在同一行寫理由"))


def review_files(base: str, head: str, added: dict[str, dict[int, str]], review: Review) -> None:
    test_lock = hook_module("test_lock")
    protected_files = hook_module("protected_files")
    guard_tests = hook_module("guard_tests")
    fork = git("merge-base", base, head).strip()
    span = f"{base}...{head}"
    numstat = git("diff", "--numstat", "--no-renames", span).splitlines()
    statuses = {}
    for line in git("diff", "--name-status", "--no-renames", span).splitlines():
        status, path = line.split("\t", 1)
        statuses[path] = status
    for row in numstat:
        _, deleted, path = row.split("\t", 2)
        if protected_files.is_reviewed(path):
            review.protected.append(path)
        if not test_lock.is_test_file(path) or statuses.get(path) == "A":
            continue
        if statuses.get(path) == "D":
            review.tests.append((path, "刪掉整個檔案"))
        elif deleted not in ("0", "-") and code_changed(guard_tests, fork, head, path):
            review.tests.append((path, "改或刪了既有的行"))
        elif any(test_lock.SKIPS_TESTS.search(line) for line in added.get(path, {}).values()):
            review.tests.append((path, "加入跳過測試的寫法"))


def code_changed(guard_tests: Any, base: str, head: str, path: str) -> bool:
    before = "\n".join(code_lines(path, git("show", f"{base}:{path}")))
    after = "\n".join(code_lines(path, git("show", f"{head}:{path}")))
    return guard_tests.added_lines(before, after) is None


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(title: str, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    if not rows:
        return []
    result = [f"#### {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    result += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return [*result, ""]


def summary(review: Review) -> str:
    quoted = [(where, f"`{text}`") for where, text in review.suppressions]
    sections = [
        *table("沒過的項目", ("位置", "原因"), review.errors),
        *table("新增的抑制註解", ("位置", "內容"), quoted),
        *table("改掉既有內容的測試檔", ("檔案", "改動"), review.tests),
        *table("動到的防線檔案", ("檔案",), [(path,) for path in review.protected]),
    ]
    if not sections:
        return (
            "沒有要審查的項目：沒有新增的抑制註解，既有的測試與防線檔案都沒動。\n"
        )
    return "\n".join(["### PR 的改動：要審查的項目", "", *sections])


def main() -> int:
    base = os.environ["BASE_SHA"]
    head = os.environ["HEAD_SHA"]
    added = added_lines(base, head)
    review = Review()
    review_suppressions(added, review)
    review_files(base, head, added, review)

    for where, problem in review.errors:
        print(f"{where}: {problem}", file=sys.stderr)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(summary(review))
    return 1 if review.errors else 0


if __name__ == "__main__":
    sys.exit(main())
