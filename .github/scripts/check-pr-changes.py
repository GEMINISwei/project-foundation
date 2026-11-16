#!/usr/bin/env python3
"""PR 的改動檢查: BASE_SHA=… HEAD_SHA=… .github/scripts/check-pr-changes.py

pr.yml 呼叫, 本機也能跑。只看這個 PR 新增的行, 既有的內容改到才整理。

擋下兩件事 (docs/foundation/development.md〈註解與文件〉〈抑制註解〉):
- 新增的抑制註解同一行沒寫理由。
- `.py`、`.ts`、`.tsx` 新增的註解不是例外。例外寫成 `例外(<測試名稱>): <理由>`,
  測試名稱要在測試檔裡; 緊接的註解行是它的接續。
  docstring、抑制註解、工具指令、設定檔與產生的檔案不檢查。

有 GITHUB_STEP_SUMMARY 時把審查要看的東西寫成表格: 沒過的項目、新增的例外與抑制註解、
改掉既有內容的測試檔、動到的防線檔案。沒有要看的項目時只有一行。
這份證據由 CI 產生, 不由 agent 描述; 測試檔與防線檔案的定義跟 hook 共用 (.agents/hooks/)。
要能在 Python 3.9 上跑 (macOS 內建)。
"""

from __future__ import annotations

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
COMMENT_SUFFIXES = (".py", ".ts", ".tsx")
GENERATED = re.compile(r"\.d\.ts$|^apps/api/migrations/versions/")
CONFIG = re.compile(r"(^|/)[^/]*\.config\.[^/]+$|(^|/)knip\.ts$")
# 呼叫子行程的警告: hook 與測試用固定參數呼叫 git、gh 是常態, 每次寫理由只是噪音。
EXEMPT_NOQA = {"S603", "S607"}

NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9]+(?:\s*,\s*[A-Z0-9]+)*))?(?P<rest>.*)$")
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(?P<rest>.*)$")
ESLINT = re.compile(r"(?://|/\*)\s*eslint-disable[\w-]*(?P<rest>.*)$")
TS_DIRECTIVE = re.compile(r"//\s*@ts-(?:expect-error|ignore)(?P<rest>.*)$")
PYTEST_SKIP = re.compile(r"pytest\.(?:mark\.skip(?:if)?|skip)\b(?P<rest>.*)$")
JS_SKIP = re.compile(r"\b(?:it|test|describe)\.skip\((?P<rest>.*)$")

EXCEPTION = re.compile(r"^例外\((?P<test>[^)]*)\):(?P<reason>.*)$")
PY_DIRECTIVE = re.compile(r"^#\s*(?:noqa|type:|fmt:|pragma|mypy:|pyright:|isort:|-\*-)")
TS_TOOL = re.compile(
    r"^/?\s*(?:eslint|@ts-|istanbul |c8 |v8 |prettier-ignore|<reference|#region|#end)"
)
PY_TEST_NAME = re.compile(r"\bdef (test_\w+)")
HUNK = re.compile(r"^@@ -\S+ \+(\d+)")
JS_TEST_NAME = re.compile(r"\b(?:it|test|describe)(?:\.\w+)?\(\s*(['\"`])(.+?)\1")

REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")
REGEX_AFTER_WORDS = {
    *("return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void"),
    *("throw", "instanceof", "yield", "await"),
}


class Line(NamedTuple):
    number: int
    text: str
    directive: bool


class Group(NamedTuple):
    path: str
    lines: list[Line]


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


def python_comments(source: str) -> list[tuple[int, str, bool]]:
    """(行號, 註解, 是否整行都是註解)。"""
    result = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                row, column = token.start
                result.append((row, token.string, not token.line[:column].strip()))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return []
    return result


def python_groups(path: str, source: str) -> list[Group]:
    groups: list[Group] = []
    previous = (0, False)
    for number, text, full_line in python_comments(source):
        directive = bool(PY_DIRECTIVE.match(text)) or (number == 1 and text.startswith("#!"))
        line = Line(number, text[1:].strip(), directive)
        if full_line and previous == (number - 1, True) and groups:
            groups[-1].lines.append(line)
        else:
            groups.append(Group(path, [line]))
        previous = (number, full_line)
    return groups


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


def typescript_groups(path: str, source: str) -> list[Group]:
    groups: list[Group] = []
    previous = (0, False)
    for number, body, full_line, block in Scanner(source).scan():
        texts = [part.strip().lstrip("*").strip() for part in body.split("\n")]
        lines = [
            Line(number + offset, text, bool(TS_TOOL.match(text)))
            for offset, text in enumerate(texts)
        ]
        joins = not block and full_line and previous == (number - 1, True)
        if joins and groups:
            groups[-1].lines.extend(lines)
        else:
            groups.append(Group(path, lines))
        previous = (number, full_line and not block)
    return groups


def in_comment_scope(path: str) -> bool:
    return (
        path.endswith(COMMENT_SUFFIXES) and not GENERATED.search(path) and not CONFIG.search(path)
    )


def test_names(head: str) -> set[str]:
    test_lock = hook_module("test_lock")
    files = [
        path
        for path in git("ls-tree", "-r", "--name-only", head).splitlines()
        if test_lock.is_test_file(path) and path.endswith(CODE_SUFFIXES)
    ]
    names: set[str] = set()
    for path in files:
        text = git("show", f"{head}:{path}")
        names.update(PY_TEST_NAME.findall(text))
        names.update(name for _, name in JS_TEST_NAME.findall(text))
    return names


class Review:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.exceptions: list[tuple[str, str, str]] = []
        self.suppressions: list[tuple[str, str]] = []
        self.tests: list[tuple[str, str]] = []
        self.protected: list[str] = []


def judge(group: Group, names: set[str]) -> tuple[str | None, str, str]:
    """(擋下的原因或 None, 測試名稱, 理由)。"""
    lines = [line for line in group.lines if not line.directive]
    match = EXCEPTION.match(lines[0].text) if lines else None
    if not match:
        return (
            "新增的註解只能是例外：寫成 `例外(<測試名稱>): <理由>`，或改用型別、lint、測試表達",
            "",
            "",
        )
    test = match.group("test").strip()
    reason = " ".join([match.group("reason").strip(), *(line.text for line in lines[1:])]).strip()
    if not match.group("reason").strip():
        return "例外要在同一行寫理由", test, reason
    if test not in names:
        return f"例外指到的測試「{test}」不在測試檔裡", test, reason
    return None, test, reason


def review_comments(head: str, added: dict[str, dict[int, str]], review: Review) -> None:
    names: set[str] | None = None
    for path, lines in added.items():
        if not in_comment_scope(path):
            continue
        source = git("show", f"{head}:{path}")
        build = python_groups if path.endswith(".py") else typescript_groups
        for group in build(path, source):
            new = [line for line in group.lines if line.number in lines and not line.directive]
            if not new:
                continue
            names = test_names(head) if names is None else names
            problem, test, reason = judge(group, names)
            where = f"{path}:{new[0].number}"
            if problem:
                review.errors.append((where, problem))
            else:
                review.exceptions.append((where, test, reason))


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
    span = f"{base}...{head}"
    numstat = git("diff", "--numstat", "--no-renames", span).splitlines()
    statuses = {}
    for line in git("diff", "--name-status", "--no-renames", span).splitlines():
        status, path = line.split("\t", 1)
        statuses[path] = status
    for row in numstat:
        _, deleted, path = row.split("\t", 2)
        if protected_files.is_protected(path):
            review.protected.append(path)
        if not test_lock.is_test_file(path) or statuses.get(path) == "A":
            continue
        if statuses.get(path) == "D":
            review.tests.append((path, "刪掉整個檔案"))
        elif deleted not in ("0", "-"):
            review.tests.append((path, "改或刪了既有的行"))
        elif any(test_lock.SKIPS_TESTS.search(line) for line in added.get(path, {}).values()):
            review.tests.append((path, "加入跳過測試的寫法"))


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
        *table("新增的例外", ("位置", "測試", "理由"), review.exceptions),
        *table("新增的抑制註解", ("位置", "內容"), quoted),
        *table("改掉既有內容的測試檔", ("檔案", "改動"), review.tests),
        *table("動到的防線檔案", ("檔案",), [(path,) for path in review.protected]),
    ]
    if not sections:
        return "沒有要審查的項目：沒有新增的例外與抑制註解，既有的測試與防線檔案都沒動。\n"
    return "\n".join(["### PR 的改動：要審查的項目", "", *sections])


def main() -> int:
    base = os.environ["BASE_SHA"]
    head = os.environ["HEAD_SHA"]
    added = added_lines(base, head)
    review = Review()
    review_comments(head, added, review)
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
