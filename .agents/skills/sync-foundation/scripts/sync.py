"""把 foundation 從上次同步之後的改動帶進子專案。

    sync.py init <repo> [commit]   建立同步紀錄 (建立子專案時執行一次)
    sync.py plan                   列出這段期間的改動與每個檔案的處理方式, 不動任何檔案
    sync.py apply                  套用, 並把同步紀錄移到 foundation 最新的 commit

子專案與 foundation 沒有共同的 git 歷史, 所以不 merge: 以 `.foundation.json` 記下的 commit 為基準,
逐檔比對「上次同步時的 foundation、現在的 foundation、子專案目前的內容」。
說明見 docs/foundation/workflow.md〈與 foundation 同步〉。只用標準函式庫, 要能在 Python 3.9 上跑。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RECORD = ".foundation.json"
REF = "refs/foundation/main"
# 歸子專案的檔案: foundation 改了也不帶。
PROJECT_FILES = ("README.md", "CHANGELOG.md", "apps/api/app/version.py", RECORD)
PROJECT_DIRS = ("docs/project/",)
# 歸 foundation 的路徑: 子專案改了要列出來, 那個修正應該回到 foundation。
FOUNDATION_PATHS = (
    "docs/foundation/",
    ".agents/",
    ".claude/",
    ".codex/",
    ".githooks/",
    ".github/",
    "tools/",
    "infra/",
    "Makefile",
)

ADOPT, MERGE, CONFLICT, MANUAL, SKIP = "adopt", "merge", "conflict", "manual", "skip"
TITLES = {
    ADOPT: "直接採用 foundation 的版本（子專案沒改過）",
    MERGE: "自動合併（兩邊改的地方不重疊）",
    CONFLICT: "有衝突：檔案裡留了衝突標記，要逐一處理",
    MANUAL: "需要判斷：沒有動這些檔案",
    SKIP: "不帶（歸子專案）",
}


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def git(
    *args: str, check: bool = True, stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    command = ["git", *args]
    result = subprocess.run(command, input=stdin, capture_output=True, check=False)  # noqa: S603 - 固定的 git 指令
    if check and result.returncode != 0:
        fail(f"git {' '.join(args)} 失敗：\n{result.stderr.decode(errors='replace').strip()}")
    return result


def text(*args: str) -> str:
    return git(*args).stdout.decode().strip()


def fetch(repo: str) -> str:
    """把 foundation 的 main 抓進本機的物件庫, 回傳它的 commit。

    不抓 tag: 子專案的部署認 v* 的 tag, foundation 的 tag 混進來會誤觸。
    """
    git("fetch", "--quiet", "--no-tags", repo, f"+refs/heads/main:{REF}")
    return text("rev-parse", REF)


def read_record() -> dict[str, str]:
    path = Path(RECORD)
    if not path.exists():
        fail(
            f"找不到 {RECORD}：這裡是 foundation 本身，或子專案還沒建立同步紀錄。\n"
            "子專案第一次使用前執行：python3 .agents/skills/sync-foundation/scripts/sync.py "
            "init <foundation 的 repo 位址>"
        )
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write_record(repo: str, commit: str) -> None:
    content = json.dumps({"repo": repo, "commit": commit}, indent=2, ensure_ascii=False)
    Path(RECORD).write_text(content + "\n", encoding="utf-8")


def tree(commit: str) -> dict[str, tuple[str, str]]:
    """這個 commit 裡每個檔案的 (mode, blob)。"""
    entries = {}
    for line in git("ls-tree", "-r", "-z", commit).stdout.decode().split("\0"):
        if line:
            meta, path = line.split("\t", 1)
            mode, _, blob = meta.split(" ")
            entries[path] = (mode, blob)
    return entries


def worktree_blob(path: str) -> str | None:
    """子專案目前這個檔案的 blob id, 不存在是 None。"""
    if os.path.islink(path):
        target = os.readlink(path).encode()
        return git("hash-object", "--stdin", "--no-filters", stdin=target).stdout.decode().strip()
    if not os.path.isfile(path):
        return None
    return text("hash-object", "--", path)


def is_project_file(path: str) -> bool:
    return path in PROJECT_FILES or path.startswith(PROJECT_DIRS)


def blob_bytes(blob: str) -> bytes:
    return git("cat-file", "blob", blob).stdout


def merge(path: str, base: str, head: str) -> tuple[int, bytes]:
    """三方合併, 回傳 (衝突數, 合併後的內容); 合不了 (例如二進位檔) 時衝突數是 -1。"""
    with tempfile.TemporaryDirectory() as directory:
        base_file, head_file = Path(directory, "base"), Path(directory, "head")
        base_file.write_bytes(blob_bytes(base))
        head_file.write_bytes(blob_bytes(head))
        labels = ("-L", "子專案", "-L", "上次同步", "-L", "foundation")
        result = git("merge-file", "-p", *labels, path, str(base_file), str(head_file), check=False)
    if result.returncode < 0 or result.returncode > 127:
        return -1, b""
    return result.returncode, result.stdout


def classify(
    path: str, base: tuple[str, str] | None, head: tuple[str, str] | None
) -> tuple[str, str, bytes]:
    """回傳 (分類, 說明, 要寫入的內容)。"""
    if is_project_file(path):
        return SKIP, "", b""
    ours = worktree_blob(path)
    base_blob = base[1] if base else None
    head_blob = head[1] if head else None
    if ours == head_blob:
        return "", "", b""  # 子專案已經是這個內容
    if ours == base_blob:
        return ADOPT, "foundation 已刪除" if head is None else "", b""
    if head is None:
        return MANUAL, "foundation 刪除了這個檔案，但子專案改過", b""
    if ours is None:
        return MANUAL, "子專案刪除了這個檔案，但 foundation 改了", b""
    if base is None:
        return MANUAL, "兩邊各自新增了內容不同的檔案", b""
    if os.path.islink(path) or "120000" in (base[0], head[0]):
        return MANUAL, "symlink 兩邊都改了", b""
    conflicts, merged = merge(path, base[1], head[1])
    if conflicts < 0:
        return MANUAL, "兩邊都改了，而且不是文字檔", b""
    return (CONFLICT if conflicts else MERGE), "", merged


def write_blob(path: str, mode: str, blob: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        target.unlink()
    if mode == "120000":
        os.symlink(blob_bytes(blob).decode(), path)
        return
    target.write_bytes(blob_bytes(blob))
    target.chmod(0o755 if mode == "100755" else 0o644)


def drift(base_tree: dict[str, tuple[str, str]], changed: set[str]) -> list[str]:
    """歸 foundation、這段期間 foundation 沒動, 但子專案與上次同步時不同的檔案。"""
    return sorted(
        path
        for path, (_, blob) in base_tree.items()
        if path.startswith(FOUNDATION_PATHS)
        and path not in changed
        and not is_project_file(path)
        and worktree_blob(path) != blob
    )


def write_change(path: str, kind: str, content: bytes, head: tuple[str, str] | None) -> None:
    if kind == ADOPT and head:
        write_blob(path, *head)
    elif kind == ADOPT:
        os.remove(path)
    elif kind in (MERGE, CONFLICT):
        Path(path).write_bytes(content)


def print_range(base: str, head: str, changed: list[str]) -> None:
    if not changed:
        print(f"已經是最新：foundation 在 {base[:12]} 之後沒有改動。")
        return
    print(f"foundation {base[:12]} → {head[:12]}\n")
    print(text("log", "--format=  %h %s", f"{base}..{head}"))


def print_report(groups: dict[str, list[str]], drifted: list[str]) -> None:
    for kind, title in TITLES.items():
        if groups[kind]:
            print(f"\n{title}：")
            print("\n".join(f"  {item}" for item in groups[kind]))
    if drifted:
        print("\n子專案改了歸 foundation 的檔案（修正應該回到 foundation）：")
        print("\n".join(f"  {path}" for path in drifted))


def run(apply: bool) -> None:
    record = read_record()
    if apply and text("status", "--porcelain"):
        fail("工作目錄有還沒 commit 的改動。先 commit 或還原，同步的結果才能單獨看 diff。")
    base, head = record["commit"], fetch(record["repo"])
    if git("cat-file", "-e", f"{base}^{{commit}}", check=False).returncode != 0:
        fail(f"在 foundation 找不到上次同步的 commit {base}。確認 {RECORD} 的 repo 與 commit。")
    base_tree, head_tree = tree(base), tree(head)
    changed = sorted(
        path
        for path in base_tree.keys() | head_tree.keys()
        if base_tree.get(path) != head_tree.get(path)
    )
    print_range(base, head, changed)

    groups: dict[str, list[str]] = {key: [] for key in TITLES}
    for path in changed:
        kind, note, content = classify(path, base_tree.get(path), head_tree.get(path))
        if kind:
            groups[kind].append(f"{path}（{note}）" if note else path)
        if apply:
            write_change(path, kind, content, head_tree.get(path))
    print_report(groups, drift(base_tree, set(changed)))
    if apply and changed:
        write_record(record["repo"], head)
        print(f"\n已套用，{RECORD} 更新到 {head[:12]}。還沒 commit。")


def init(repo: str, commit: str | None) -> None:
    if Path(RECORD).exists():
        fail(f"{RECORD} 已經存在：{Path(RECORD).read_text(encoding='utf-8').strip()}")
    head = fetch(repo)
    commit = text("rev-parse", "--verify", f"{commit}^{{commit}}") if commit else head
    write_record(repo, commit)
    print(f"已建立 {RECORD}：從 {commit[:12]} 開始同步。把它 commit 進去。")


def main(argv: list[str]) -> None:
    if len(argv) in (2, 3) and argv[0] == "init":
        init(argv[1], argv[2] if len(argv) == 3 else None)
    elif argv in (["plan"], ["apply"]):
        run(apply=argv == ["apply"])
    else:
        fail("用法：sync.py init <repo> [commit] | plan | apply")


if __name__ == "__main__":
    os.chdir(text("rev-parse", "--show-toplevel"))
    main(sys.argv[1:])
