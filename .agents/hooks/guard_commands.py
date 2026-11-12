#!/usr/bin/env python3
"""指令守衛: Claude 與 Codex 的 PreToolUse hook, 只擋確認點 (decisions.md 11)。

用法 (由 .claude/settings.json 與 .codex/hooks.json 呼叫): guard_commands.py <claude|codex>

- deny: push 到 main、略過 git hook、合併／轉 Ready、發布與部署、自己寫放行
- 確認: publish.sh、`gh api` 寫入、`gh run rerun`、有開著的 PR 時開新分支。
  Claude 回 ask; Codex 不支援 ask, 回 deny 並說明怎麼取得同意。

只認常見寫法, 不追求繞不過: 換寫法擋不住是已知的取捨, 由 CI 與審查補。只用標準函式庫。
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path

import approvals
import branch_lock
from test_lock import repo_root

SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&"}
WRAPPERS = {"sudo", "env", "command", "exec", "time", "nohup", "xargs"}
SHELLS = {"sh", "bash", "zsh"}
PYTHONS = {"python", "python3", "uv", "uvx"}
# 直譯器執行內嵌程式的旗標: 用來認出 `python -c "runpy…approve.py"` 這類換寫法的申請。
INLINE_CODE_FLAGS = {"-c", "-e", "-E", "--eval", "-p", "--print"}
READ_ONLY = {"cat", "ls", "head", "tail", "less", "stat", "file", "wc", "grep", "rg", "jq", "test"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUSH_OPTIONS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
MAIN_REFS = {"main", "refs/heads/main"}
CONFIG_READS = {"get", "list"}
CONFIG_WRITES = {"set", "unset", "rename-section", "remove-section", "edit"}
CONFIG_WRITE_FLAGS = {"--add", "--replace-all", "--unset", "--unset-all", "--edit", "-e"}
PUBLISH_COMMAND = ".agents/skills/release/scripts/publish.sh"
GH_API_FIELDS = {"-f", "--raw-field", "-F", "--field", "--input"}
# `<<EOF`、`<<-'EOF'`; `<<<` 是 here-string, 不算。
HEREDOC = re.compile(r"(?<!<)<<-?(?!<)\s*(['\"]?)(\w+)\1")

DENY_MAIN = "不可以直接 push 到 main：main 只透過 PR 前進。"
DENY_HOOKS = (
    "不要略過或關掉 git hook（--no-verify、commit -n、core.hooksPath）：照 hook 的訊息修正。"
)
DENY_MERGE = "合併 PR 與轉 Ready for review 由使用者做。回報 PR 狀態，等使用者處理。"
DENY_DEPLOY = (
    f"發布與部署只能用 `{PUBLISH_COMMAND} <版號> [--prerelease]`，先用 preview.sh 給使用者看、"
    "使用者同意後才執行（release skill）。重新部署或回滾由使用者自己觸發。"
)
DENY_SELF_APPROVAL = (
    f"放行只能用 `{' '.join(approvals.COMMAND)} <test|protected|branch> …` 申請，它會跳確認；"
    "不要直接寫放行檔或換寫法呼叫。"
)


def logical_lines(command: str) -> str:
    """去掉 heredoc 的內容 (那是資料), 並把換行當成指令的分隔。"""
    lines: list[str] = []
    delimiters: list[str] = []
    pending = ""
    for line in command.split("\n"):
        if delimiters:
            if line.strip() == delimiters[0]:
                delimiters.pop(0)
            continue
        delimiters += [match.group(2) for match in HEREDOC.finditer(line)]
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        lines.append(pending + line)
        pending = ""
    return " ; ".join([*lines, pending])


def simple_commands(command: str) -> Iterator[list[str]]:
    """拆成一個個簡單指令的 argv; `bash -c`、`eval` 的內容也展開。"""
    lexer = shlex.shlex(logical_lines(command), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # 引號沒閉合: 交給 shell 自己報錯
        return
    current: list[str] = []
    for token in [*tokens, ";"]:
        if token not in SEPARATORS:
            current.append(token)
            continue
        argv = strip_prefixes(current)
        current = []
        if not argv:
            continue
        if argv[0] in SHELLS and "-c" in argv[1:-1]:
            yield from simple_commands(argv[argv.index("-c") + 1])
        elif argv[0] == "eval" and argv[1:]:
            yield from simple_commands(" ".join(argv[1:]))
        else:
            yield argv


def strip_prefixes(argv: list[str]) -> list[str]:
    """去掉開頭的 `FOO=1` 與 `sudo`、`env` 這類包裝。"""
    index = 0
    while index < len(argv) and ("=" in argv[index].split("/")[0] or argv[index] in WRAPPERS):
        index += 1
    return argv[index:]


def program(argv: list[str]) -> str:
    return argv[0].rsplit("/", 1)[-1]


def current_branch(cwd: str) -> str:
    return approvals.git(Path(cwd), "symbolic-ref", "--short", "-q", "HEAD") or ""


def git_subcommand(argv: list[str]) -> tuple[str, list[str]]:
    index = 1
    while index < len(argv) and argv[index].startswith("-"):
        index += 2 if argv[index] in GIT_OPTIONS_WITH_VALUE else 1
    return (argv[index], argv[index + 1 :]) if index < len(argv) else ("", [])


def pushes_to_main(args: list[str], cwd: str) -> bool:
    short_flags = [arg for arg in args if arg.startswith("-") and not arg.startswith("--")]
    if "--dry-run" in args or any("n" in flags for flags in short_flags):
        return False
    positional: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in PUSH_OPTIONS_WITH_VALUE:
            skip = True
        elif not arg.startswith("-"):
            positional.append(arg)
    refspecs = positional[1:]
    if not refspecs or refspecs == ["HEAD"]:
        return current_branch(cwd) == "main"
    return any(refspec.lstrip("+").split(":")[-1] in MAIN_REFS for refspec in refspecs)


def skips_hooks(subcommand: str, args: list[str]) -> bool:
    """`--no-verify` 與 commit 的 `-n` (push 的 `-n` 是 dry-run)。"""
    if "--no-verify" in args:
        return True
    short_flags = [arg for arg in args if arg.startswith("-") and not arg.startswith("--")]
    return subcommand == "commit" and any("n" in flags for flags in short_flags)


def changes_hooks_path(argv: list[str], subcommand: str, args: list[str]) -> bool:
    options = argv[1 : len(argv) - len(args) - 1]
    if any(option.lower().startswith("core.hookspath") for option in options):
        return True
    if subcommand != "config" or "core.hookspath" not in [arg.lower() for arg in args]:
        return False
    positional = [arg for arg in args if not arg.startswith("-")]
    action = positional[0] if positional[0] in CONFIG_READS | CONFIG_WRITES else None
    if action in CONFIG_READS:
        return False
    key = [arg.lower() for arg in positional].index("core.hookspath")
    values = positional[key + 1 :]
    writes = action in CONFIG_WRITES or bool(CONFIG_WRITE_FLAGS & set(args)) or bool(values)
    return writes and values != [".githooks"]


def git_violation(argv: list[str], cwd: str) -> str | None:
    subcommand, args = git_subcommand(argv)
    if subcommand == "push" and pushes_to_main(args, cwd):
        return DENY_MAIN
    if subcommand in {"commit", "push", "merge"} and skips_hooks(subcommand, args):
        return DENY_HOOKS
    if changes_hooks_path(argv, subcommand, args):
        return DENY_HOOKS
    return None


def gh_violation(argv: list[str]) -> str | None:
    if argv[1:3] == ["pr", "merge"] or (argv[1:3] == ["pr", "ready"] and "--undo" not in argv):
        return DENY_MERGE
    if argv[1:2] == ["release"] and argv[2:3] and argv[2] in {"create", "edit", "delete"}:
        return DENY_DEPLOY
    deploy_workflow = any(arg.lower().startswith("deploy") for arg in argv[3:])
    if argv[1:3] == ["workflow", "run"] and deploy_workflow:
        return DENY_DEPLOY
    return None


def publishes_another_way(argv: list[str]) -> bool:
    if argv[0] == PUBLISH_COMMAND:
        return False
    script = PUBLISH_COMMAND.rsplit("/", 1)[-1]
    positional = [arg for arg in argv[1:] if not arg.startswith("-")]
    return program(argv) == script or (
        program(argv) in SHELLS and bool(positional) and positional[0].endswith(script)
    )


def self_approval(argv: list[str]) -> bool:
    """換寫法執行 approve.py, 或寫入放行檔。只讀的不算。"""
    if argv[: len(approvals.COMMAND)] == approvals.COMMAND:
        return False
    script = approvals.COMMAND[1].rsplit("/", 1)[-1]
    positional = [arg for arg in argv[1:] if not arg.startswith("-")]
    code = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in INLINE_CODE_FLAGS]
    runs_script = (
        program(argv) == script
        or (program(argv) in PYTHONS and bool(positional) and positional[0].endswith(script))
        or any(script in snippet for snippet in code)
    )
    targets = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in REDIRECTS]
    arguments = [arg for arg in argv[1:] if arg not in targets and arg not in REDIRECTS]
    reads_json = program(argv) in PYTHONS and argv[1:3] == ["-m", "json.tool"]
    reads_only = program(argv) in READ_ONLY or (reads_json and len(positional) <= 2)
    writes = any(approvals.NAME in target for target in targets) or (
        not reads_only and any(approvals.NAME in arg for arg in arguments)
    )
    return runs_script or writes


def violation(argv: list[str], cwd: str) -> str | None:
    if self_approval(argv):
        return DENY_SELF_APPROVAL
    if publishes_another_way(argv):
        return DENY_DEPLOY
    if program(argv) == "git":
        return git_violation(argv, cwd)
    if program(argv) == "gh":
        return gh_violation(argv)
    return None


def gh_api_writes(argv: list[str]) -> bool:
    """GET 以外的方法 (帶欄位而沒指定方法時 gh 用 POST); GraphQL 只看有沒有 mutation。"""
    args = argv[2:]
    if "graphql" in args:
        return any("mutation" in arg for arg in args)
    method = ""
    for index, arg in enumerate(args):
        name, _, value = arg.partition("=")
        if name in {"-X", "--method"}:
            method = (value or (args[index + 1 : index + 2] or [""])[0]).upper()
    has_fields = any(arg.partition("=")[0] in GH_API_FIELDS for arg in args)
    return (method or ("POST" if has_fields else "GET")) != "GET"


def needs_confirmation(argv: list[str]) -> str | None:
    if program(argv) != "gh":
        return None
    if argv[1:2] == ["api"] and gh_api_writes(argv):
        return "這個 API 會改 GitHub 上的狀態（可能合併、發布或觸發部署）"
    if argv[1:3] == ["run", "rerun"]:
        return "重跑 workflow 可能重新部署（Deploy 的 run）"
    return None


def new_branch(argv: list[str], cwd: str) -> str | None:
    """這個指令會開始的新分支 (開分支、worktree、PR); 不是的話回傳 None。"""
    if program(argv) == "gh":
        if argv[1:3] != ["pr", "create"]:
            return None
        head = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in {"--head", "-H"}]
        return head[0] if head else current_branch(cwd)
    if program(argv) != "git":
        return None
    subcommand, args = git_subcommand(argv)
    flags = {arg for arg in args if arg.startswith("-")}
    positional = [arg for arg in args if not arg.startswith("-")]
    if subcommand == "switch" and {"-c", "-C", "--create", "--force-create"} & flags:
        return positional[0] if positional else ""
    if subcommand == "checkout" and {"-b", "-B"} & flags:
        return positional[0] if positional else ""
    if subcommand == "branch" and not flags and positional:
        return positional[0]
    if subcommand == "worktree" and positional[:1] == ["add"]:
        named = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg in {"-b", "-B"}]
        if named:
            return named[0]
        return positional[2] if len(positional) > 2 else positional[-1].rsplit("/", 1)[-1]
    return None


def parallel_branches(commands: list[list[str]], cwd: str) -> list[str]:
    """還有開著的 PR 時, 要開始而且還沒被放行的分支。"""
    found = [new_branch(argv, cwd) for argv in commands]
    branches = {branch for branch in found if branch is not None}
    root = repo_root(Path(cwd))
    if not branches or root is None:
        return []
    pending = branches - approvals.approved(root, "branch")
    return sorted(pending) if pending and branch_lock.open_prs(cwd) else []


def decide(decision: str, reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    json.dump(output, sys.stdout, ensure_ascii=False)


def confirm(agent: str, reason: str, codex_next_step: str) -> None:
    if agent == "codex":
        decide("deny", f"{reason}。{codex_next_step}")
    else:
        decide("ask", f"{reason}，確認使用者同意。")


def main() -> int:
    agent = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    cwd = payload.get("cwd") or "."
    commands = list(simple_commands(command if isinstance(command, str) else shlex.join(command)))
    for argv in commands:
        reason = violation(argv, cwd)
        if reason:
            decide("deny", reason)
            return 0
    for argv in commands:
        reason = needs_confirmation(argv)
        if reason:
            confirm(agent, reason, "向使用者說明要做什麼，請使用者自己執行。")
            return 0
    branches = parallel_branches(commands, cwd)
    if branches:
        approve = " ".join([*approvals.COMMAND, "branch", *branches])
        reason = "使用者還有開著的 PR：一次一個 PR，插隊要使用者同意（hotfix skill）"
        confirm(agent, reason, f"使用者同意插隊後執行 `{approve}`，它會跳確認。")
        return 0
    # permissions.ask 也列了它; 這裡再回 ask 是因為權限模式可能略過設定檔。Codex 由 rule 負責。
    if agent == "claude" and any(argv[0] == PUBLISH_COMMAND for argv in commands):
        decide("ask", "發布 release 會直接部署：確認使用者看過 preview.sh 的內容並同意發布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
