"""make release <版號>: 準備一次發版 (改版號與 CHANGELOG, 切到發版分支)。

    make release 0.1.0

它只改檔與切分支, 不 commit、不 push、不建 tag: 看過 diff 後 commit、開 PR
(標題 `chore(release): v<版號>`), 合併後在 GitHub 發布 release
(tag `v<版號>`、target `main`) 才會部署。

改檔之前先檢查, 任何一項不過就停、什麼都不改:
版號是 X.Y.Z 且比目前的大、CHANGELOG 還沒有這個版號、[Unreleased] 不是空的、工作目錄乾淨、
在 main 且與 origin/main 一致、tag 與發版分支都不存在。
"""

from __future__ import annotations

import re
import subprocess

from tools.env import REPO_ROOT, app_version, deny_on_production, fail, load_env

USAGE = "用法：make release <版號>（例如 make release 0.1.0）"
VERSION_FILE = REPO_ROOT / "apps/api/app/version.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
UNRELEASED = "## [Unreleased]"


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        fail(f"git {' '.join(args)} 失敗：{result.stderr.strip()}")
    return result.stdout.strip()


def ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--quiet", "--verify", ref],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def as_numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def unreleased_entries(changelog: str) -> str:
    """[Unreleased] 段落的內容 (到下一個版本標題為止)。"""
    if UNRELEASED not in changelog:
        fail(f"CHANGELOG.md 找不到「{UNRELEASED}」段落")
    body = changelog.split(UNRELEASED, 1)[1]
    return re.split(r"^## \[", body, maxsplit=1, flags=re.M)[0].strip()


def preflight(version: str, current: str, changelog: str) -> str:
    if not VERSION_PATTERN.match(version):
        fail("版號要是 X.Y.Z（每段是數字，不可有前導零），例如 make release 0.1.0")
    if as_numbers(version) <= as_numbers(current):
        fail(f"新版號 {version} 必須大於目前的 {current}")
    if f"## [{version}]" in changelog:
        fail(f"CHANGELOG.md 已經有 [{version}] 的段落")
    if not unreleased_entries(changelog):
        fail("CHANGELOG.md 的 [Unreleased] 是空的，先寫下這一版改了什麼")
    if status := git("status", "--porcelain"):
        fail(f"工作目錄有沒 commit 的改動，先 commit 或還原再發版：\n{status}")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch != "main":
        fail(f"要在 main 上發版（目前在 {branch or 'detached HEAD'}）")
    git("fetch", "--quiet", "--tags", "origin")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        fail("本機 main 與 origin/main 不一致：先 git pull；本機多出的 commit 要走 PR")
    if ref_exists(f"refs/tags/v{version}"):
        fail(f"tag v{version} 已經存在")
    release_branch = f"chore/release-v{version}"
    if ref_exists(f"refs/heads/{release_branch}") or ref_exists(
        f"refs/remotes/origin/{release_branch}"
    ):
        fail(f"分支 {release_branch} 已經存在：上次發版沒有收尾，先合併或刪掉它")
    return release_branch


def run(_name: str, args: list[str]) -> None:
    if len(args) != 1:
        fail(USAGE)
    deny_on_production(load_env(required=False), "make release")
    version, current = args[0], app_version()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    release_branch = preflight(version, current, changelog)

    git("switch", "--quiet", "-c", release_branch)
    source = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        source.replace(f'APP_VERSION = "{current}"', f'APP_VERSION = "{version}"'),
        encoding="utf-8",
    )
    CHANGELOG.write_text(
        changelog.replace(UNRELEASED, f"{UNRELEASED}\n\n## [{version}]", 1), encoding="utf-8"
    )
    print(f"已改成 v{version}，目前在分支 {release_branch}。接下來：")
    print("  1. git diff 看過改動")
    print(f"  2. commit 並開 PR，標題 chore(release): v{version}")
    print(f"  3. 合併後在 GitHub 發布 release：tag v{version}、target main")
