"""make backup: 備份與還原。

    make backup                         備份資料庫、上傳的檔案與當下的 log (存在 backups/)
    make backup prune <組數>            只保留最近幾組備份
    make backup restore db [檔案]       還原資料庫 (只接受目前版本的備份)
    make backup restore uploads [檔案]  還原上傳的檔案 (任何版本的備份都可以)

備份期間會停掉所有會寫資料的服務 (對外入口、web、api 與 worker, 等進行中的請求與任務做完),
資料庫與上傳的檔案才是同一個時間點; 完成或失敗都會開回來。資料庫與上傳的檔案都成功才留下這一組備份。

還原之前一定先完整備份一次: 選錯檔案還退得回來, 這次備份失敗就不還原。還原失敗時服務維持停止,
不會自動接回流量。只需要 postgres 在執行, 所以部署失敗後停在
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
from tools.compose import (
    WRITERS,
    container,
    container_running,
    containers,
    entry_responds,
    paused,
)
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
        for name in (name for service in LOGGED_SERVICES for name in containers(env, service)):
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
    backups.ensure_private_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = backups.BACKUP_DIR / f"{env['COMPOSE_PROJECT_NAME']}_v{app_version()}_{stamp}"
    dump, uploads = (stem.with_name(f"{stem.name}.{kind}") for kind in ("dump", "tar"))
    # 先寫到 .partial, 兩份都成功才一起改名: 任何一份失敗都不會留下看起來完整的半組備份。
    partial = {final: final.with_name(final.name + ".partial") for final in (dump, uploads)}
    pg_dump = 'exec pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

    # 只關入口不夠: 已經進到 web、api 的請求還在跑, 會在匯出途中寫入, 資料庫與上傳的檔案就
    # 不是同一個時間點。全部停下 (docker stop 會等它們收尾) 才開始。
    with paused(env, WRITERS, resume_on_failure=True):
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
    apply_restore(env, target, path)
    print(f"還原完成：{backup.label}")
    other = {"dump": "tar", "tar": "dump"}[kind]
    sibling = path.with_name(f"{backup.stem}.{other}")
    if sibling.is_file():
        # 資料庫的紀錄會指到上傳的檔案: 兩邊要來自同一組備份才對得起來。
        other_target = "uploads" if target == "db" else "db"
        print(f"同一組備份的另一半還沒還原：make backup restore {other_target} {sibling}")


def apply_restore(env: dict[str, str], target: str, path: Path) -> None:
    """實際還原, 不問確認: 人下的指令由 `restore()` 先問過, 自動化的驗證直接呼叫這裡。"""
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


ROUNDTRIP_MARKER = "backup_roundtrip_marker"
# 備份之後才出現的資料: 用平台自己的資料表, 不依賴任何模組。
MARKER_INSERT = (
    "INSERT INTO audit_logs (id, created_at, event, actor_id, ip, request_id, committed, data) "
    "VALUES (gen_random_uuid(), now(), 'backup_roundtrip_marker', '-', '-', '-', true, '{}')"
)
MARKER_COUNT = "SELECT count(*) FROM audit_logs WHERE event = 'backup_roundtrip_marker'"


def _psql(env: dict[str, str], query: str) -> str:
    script = 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "$1"'
    command = ["docker", "exec", container(env, "postgres"), "sh", "-c", script, "sh", query]
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout.strip()


def _marker_file_exists(env: dict[str, str]) -> bool:
    command = uploads_command(env, "test", "-e", f"{UPLOADS_DIR}/.{ROUNDTRIP_MARKER}")
    return subprocess.run(command, check=False).returncode == 0


def verify_roundtrip(env: dict[str, str]) -> None:
    """實際備份、改資料、再還原, 確認資料回到備份當時的樣子 (make e2e check 呼叫)。

    還原指令壞掉的時候沒有任何症狀, 要到真的需要還原才會發現; 所以每次 CI 都對拋棄式的環境
    實際做一次。備份檔寫在暫存目錄, 不留在 backups/。
    """
    original = backups.BACKUP_DIR
    with tempfile.TemporaryDirectory() as directory:
        backups.BACKUP_DIR = Path(directory)
        try:
            backup_all(env)
            dump, uploads = (
                backups.list_backups("dump")[0].path,
                backups.list_backups("tar")[0].path,
            )

            _psql(env, MARKER_INSERT)
            marker_file = f"{UPLOADS_DIR}/.{ROUNDTRIP_MARKER}"
            subprocess.run(uploads_command(env, "touch", marker_file, writable=True), check=True)
            if _psql(env, MARKER_COUNT) != "1" or not _marker_file_exists(env):
                fail("備份還原驗證：標記沒有寫進去，驗證本身有問題")

            apply_restore(env, "db", dump)
            apply_restore(env, "uploads", uploads)

            if _psql(env, MARKER_COUNT) != "0":
                fail("備份還原驗證：資料庫還原之後，備份之後才新增的紀錄還在")
            if _marker_file_exists(env):
                fail("備份還原驗證：上傳的檔案還原之後，備份之後才新增的檔案還在")
            if not entry_responds(env):
                fail("備份還原驗證：還原之後入口沒有回應")
        finally:
            backups.BACKUP_DIR = original
    print("備份還原驗證：通過")


def run(_name: str, args: list[str]) -> None:
    env = load_env()
    require_env(env, "COMPOSE_PROJECT_NAME")
    require_mode(env)
    if not args:
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
