"""make backup: 備份與還原。

    make backup                         備份資料庫、上傳的檔案與當下的 log (存在 backups/)
    make backup prune <組數>            只保留最近幾組備份
    make backup restore db [檔案]       還原資料庫 (只接受目前版本的備份)
    make backup restore uploads [檔案]  還原上傳的檔案 (任何版本的備份都可以)

備份期間會停掉所有會寫資料的來源 (對外入口與 worker, 等進行中的請求與任務做完), 資料庫與上傳的
檔案才是同一個時間點; 完成或失敗都會開回來。資料庫與上傳的檔案都成功才留下這一組備份。

還原之前一定先完整備份一次: 選錯檔案還退得回來, 這次備份失敗就不還原。還原期間連 web 與 api
也停掉; 還原失敗時服務維持停止, 不會自動接回流量。只需要 postgres 在執行, 所以部署失敗後停在
維護狀態時一樣能還原。
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from tools import backups
from tools.compose import WRITERS, container, container_running, paused
from tools.env import app_version, confirm, fail, load_env, require_env, require_mode

USAGE = (__doc__ or "").split("\n\n")[1]
UPLOADS_DIR = "/app/uploads"
LOGGED_SERVICES = ("nginx", "web", "api", "worker", "postgres")


def volume(env: dict[str, str], name: str) -> str:
    return f"{env['COMPOSE_PROJECT_NAME']}_{env['MODE']}_{name}"


def uploads_command(env: dict[str, str], *command: str, writable: bool = False) -> list[str]:
    """對 uploads volume 執行指令。用一次性的容器: api 停著的時候也要能備份與還原。"""
    postgres = container(env, "postgres")
    image = subprocess.run(
        ["docker", "inspect", "--format", "{{.Config.Image}}", postgres],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    mount = f"{volume(env, 'uploads')}:{UPLOADS_DIR}{'' if writable else ':ro'}"
    # 借用 postgres 的映像檔: 主機上一定有, 不必為了 tar 再拉一個。
    return ["docker", "run", "--rm", "-i", "--entrypoint", "", "-v", mount, image, *command]


def dump_to(path: Path, command: list[str]) -> None:
    with path.open("wb") as output:
        subprocess.run(command, stdout=output, check=True)


def save_logs(env: dict[str, str], path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        for service in LOGGED_SERVICES:
            name = container(env, service)
            with (Path(directory) / f"{name}.log").open("wb") as output:
                subprocess.run(
                    ["docker", "logs", "--timestamps", name],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        with tarfile.open(path, "w:gz") as archive:
            archive.add(directory, arcname=".")
    print(f"已備份：{path.relative_to(backups.BACKUP_DIR.parent)}")


def backup_all(env: dict[str, str]) -> None:
    if not container_running(env, "postgres"):
        fail(f"{container(env, 'postgres')} 沒有在執行，請先 make start")
    backups.BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = backups.BACKUP_DIR / f"{env['COMPOSE_PROJECT_NAME']}_v{app_version()}_{stamp}"
    dump, uploads = (stem.with_name(f"{stem.name}.{kind}") for kind in ("dump", "tar"))
    # 先寫到 .partial, 兩份都成功才一起改名: 任何一份失敗都不會留下看起來完整的半組備份。
    partial = {final: final.with_name(final.name + ".partial") for final in (dump, uploads)}
    pg_dump = 'exec pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

    # api 不必停: 入口關了就沒有請求進得來, 剩下會自己寫資料的只有 worker。
    with paused(env, ("nginx", "worker"), resume_on_failure=True):
        try:
            dump_to(
                partial[dump], ["docker", "exec", container(env, "postgres"), "sh", "-c", pg_dump]
            )
            # 不壓縮: 圖片與影片本身已經壓過。
            dump_to(
                partial[uploads], uploads_command(env, "tar", "-C", UPLOADS_DIR, "-cf", "-", ".")
            )
            for final, temporary in partial.items():
                temporary.replace(final)
                print(f"已備份：{final.relative_to(backups.BACKUP_DIR.parent)}")
        finally:
            for temporary in partial.values():
                temporary.unlink(missing_ok=True)
        try:
            save_logs(env, stem.with_name(stem.name + ".logs.tar.gz"))
        except (subprocess.CalledProcessError, OSError):
            print("警告：log 沒有備份成功（資料庫與上傳的檔案已備份）")


def is_fresh_host(env: dict[str, str]) -> bool:
    result = subprocess.run(
        ["docker", "volume", "ls", "-q"], capture_output=True, text=True, check=True
    )
    return volume(env, "postgres_data") not in result.stdout.split()


def choose(kind: str, version: str | None) -> Path:
    found = backups.list_backups(kind, version)
    if not found:
        scope = f" v{version} " if version else ""
        fail(f"backups/ 裡沒有{scope}的備份")
    print("備份（新到舊）：")
    for index, backup in enumerate(found, start=1):
        print(f"  {index}) {backup.label}")
    answer = input("選擇編號：").strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(found):
        fail("無效的編號")
    return found[int(answer) - 1].path


def restore(env: dict[str, str], target: str, file: str | None) -> None:
    kind = {"db": "dump", "uploads": "tar"}[target]
    version = app_version() if target == "db" else None
    path = Path(file).resolve() if file else choose(kind, version)
    backup = backups.parse(path)
    if not path.is_file() or backup is None or backup.kind != kind:
        fail(f"不是有效的備份檔：{path}（檔名應為 <專案>_v<版號>_<日期>_<時間>.{kind}）")
    if version and backup.version != version:
        # 別版的資料表結構可能跟目前的程式對不上。
        fail(f"這是 v{backup.version} 的備份，目前是 v{version}；先部署回 v{backup.version} 再還原")
    what = "資料庫的資料" if target == "db" else "所有上傳的檔案"
    confirm(f"將先完整備份一次，再以 {backup.label} 的備份取代目前{what}，確定？")

    if target == "db":
        # 整個還原包在一個交易裡: 中途失敗就整批回滾, 資料庫維持還原之前的樣子。
        script = (
            "exec pg_restore --clean --if-exists --no-owner --no-acl "
            '--single-transaction --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
        )
        command = ["docker", "exec", "-i", container(env, "postgres"), "sh", "-c", script]
    else:
        # 先完整解開到暫存目錄再換上去: 備份檔壞掉或磁碟滿了的時候, 原本的檔案還在。
        script = (
            'set -e; new="$1/.restoring"; rm -rf "$new"; mkdir "$new"; '
            'tar -C "$new" -xf - || { rm -rf "$new"; exit 1; }; '
            'find "$1" -mindepth 1 -maxdepth 1 ! -name .restoring -exec rm -rf {} +; '
            'find "$new" -mindepth 1 -maxdepth 1 -exec mv {} "$1/" \\;; rmdir "$new"'
        )
        command = uploads_command(env, "sh", "-c", script, "_", UPLOADS_DIR, writable=True)

    # 還原期間不能有任何東西讀寫資料; 失敗時狀態不明, 服務維持停止等人確認。
    with paused(env, WRITERS, resume_on_failure=False):
        backup_all(env)
        with path.open("rb") as source:
            if subprocess.run(command, stdin=source, check=False).returncode != 0:
                fail("還原失敗（原因見上方訊息）：資料維持還原之前的樣子")
    print(f"還原完成：{backup.label}")
    other = {"dump": "tar", "tar": "dump"}[kind]
    sibling = path.with_name(f"{backup.stem}.{other}")
    if sibling.is_file():
        # 資料庫的紀錄會指到上傳的檔案: 兩邊要來自同一組備份才對得起來。
        other_target = "uploads" if target == "db" else "db"
        print(f"同一組備份的另一半還沒還原：make backup restore {other_target} {sibling}")


def run(_name: str, args: list[str]) -> None:
    env = load_env()
    require_env(env, "COMPOSE_PROJECT_NAME")
    require_mode(env)
    if not args:
        backup_all(env)
    elif args == ["allow-fresh"]:
        # 部署流程用: 第一次部署還沒有資料, 沒有東西可以備份。
        if is_fresh_host(env):
            print("還沒有任何資料（第一次部署），略過備份")
        else:
            backup_all(env)
    elif len(args) == 2 and args[0] == "prune" and args[1].isdigit() and int(args[1]) > 0:
        doomed = backups.to_prune(int(args[1]))
        for path in doomed:
            os.remove(path)
        print(f"保留最近 {args[1]} 組，刪除 {len(doomed)} 個檔案")
    elif len(args) in (2, 3) and args[0] == "restore" and args[1] in ("db", "uploads"):
        restore(env, args[1], args[2] if len(args) == 3 else None)
    else:
        fail(USAGE)
