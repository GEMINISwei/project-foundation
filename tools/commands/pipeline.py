"""make pipeline: 部署流程呼叫的步驟 (.github/workflows/deploy.yml)。

    make pipeline backup        部署前的備份; 還沒有任何資料的主機 (第一次部署) 略過
    make pipeline revision      印出資料庫目前的 migration 版本; 還沒有資料時不印
    make pipeline migration-direction <versions 目錄> [資料庫的版本]
                                確認要部署的版本不會讓資料庫往回

這一組是給部署流程用的, 不列在 make help 裡。要部署請發布 release (release skill),
要手動備份用 make backup。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tools.commands import backup
from tools.compose import docker_exec
from tools.env import fail, load_env, require_env, require_mode

USAGE = (__doc__ or "").split("\n\n", 1)[1].rstrip()


def print_revision(env: dict[str, str]) -> None:
    """全新的主機 (連資料 volume 都沒有) 什麼都不印。"""
    volume = f"{env['COMPOSE_PROJECT_NAME']}_{require_mode(env)}_postgres_data"
    volumes = subprocess.run(
        ["docker", "volume", "ls", "-q"], capture_output=True, text=True, check=True
    ).stdout.split()
    if volume not in volumes:
        return
    script = 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq -c "$1"'

    def query(sql: str) -> str:
        # 有資料卻連不上資料庫時讓它失敗: 主機的狀態不是預期的, 不能當成「沒有版本」放行。
        result = docker_exec(env, "postgres", ["sh", "-c", script, "sh", sql], capture=True)
        return result.stdout.strip()

    # 先確認版本表存在: 第一次部署在 migration 之前就失敗時, volume 已經建立但還沒有這張表。
    # 不能合成一句用 WHERE 判斷: PostgreSQL 在執行之前就檢查表名, 表不存在整句都會出錯,
    # 部署前的檢查就一直失敗, 修好了也重新部署不了。
    if query("SELECT to_regclass('public.alembic_version') IS NOT NULL") != "t":
        return
    print(query("SELECT version_num FROM alembic_version"))


def check_migration_direction(versions: str, db_revision: str) -> None:
    """主機資料庫的版本必須在要部署的這一版裡。migration 只往前, 所以資料庫比程式新
    (兩版之間多了 migration) 就不能回滾到這一版。"""
    if not db_revision:
        print("資料庫還沒有跑過 migration，放行")
        return
    known = set()
    for path in Path(versions).glob("*.py"):
        known.update(re.findall(r"^revision[^=]*=\s*['\"]([^'\"]+)['\"]", path.read_text(), re.M))
    if db_revision in known:
        print(f"資料庫的版本 {db_revision} 在這一版的 migration 裡，放行")
        return
    fail(
        f"資料庫的版本 {db_revision} 比要部署的這一版新（或兩邊分岔），不能部署。可以：\n"
        "  - 往前修：修好之後發一個新版本\n"
        "  - 還原部署前的備份：在主機上 make backup restore db（會失去備份之後的資料）"
    )


def run(_name: str, args: list[str]) -> None:
    if len(args) in (2, 3) and args[0] == "migration-direction":
        # 在 CI 的 runner 上執行, 那裡沒有 .env。
        check_migration_direction(args[1], args[2] if len(args) == 3 else "")
    elif args == ["backup"]:
        env = load_env()
        require_env(env, "COMPOSE_PROJECT_NAME")
        require_mode(env)
        if backup.is_fresh_host(env):
            print("還沒有任何資料（第一次部署），略過備份")
        else:
            backup.backup_all(env)
    elif args == ["revision"]:
        env = load_env()
        require_env(env, "COMPOSE_PROJECT_NAME")
        print_revision(env)
    else:
        fail(USAGE)
