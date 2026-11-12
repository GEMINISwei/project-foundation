"""make db: 資料庫與帳號的管理指令。

    make db psql               開一個 psql (會直接連上正在使用的資料庫)
    make db superuser          建立超級管理者 (第一個、之後新增的、失聯時的救援都用它)
    make db revoke-sessions    讓所有人都要重新登入
    make db migration "說明"   依 model 的變動產生一支 migration (僅開發環境)
    make db reset              清空資料庫並重建 (僅開發環境)
    make db revision           印出資料庫目前的 migration 版本 (部署流程用; 還沒有資料時不印)

還原備份見 make backup。
"""

from __future__ import annotations

import subprocess

from tools.compose import app_cli, docker_exec
from tools.env import confirm, deny_on_production, fail, load_env, require_env, require_mode

USAGE = (__doc__ or "").split("\n\n")[1]

MIGRATION_REMINDER = """
產生完成。請自己讀一遍那個檔案，自動產生的內容固定會漏三件事：
  - 資料：往有資料的表加 NOT NULL 欄位，它只寫 ADD COLUMN，不會回填
  - 改名：欄位或表改名會被看成刪一個、加一個，照著跑資料就沒了
  - 不能在交易裡執行的 DDL（CREATE INDEX CONCURRENTLY）"""


def print_revision(env: dict[str, str]) -> None:
    """部署前用來確認資料庫不會往回。全新的主機 (連資料 volume 都沒有) 什麼都不印。"""
    volume = f"{env['COMPOSE_PROJECT_NAME']}_{require_mode(env)}_postgres_data"
    volumes = subprocess.run(
        ["docker", "volume", "ls", "-q"], capture_output=True, text=True, check=True
    ).stdout.split()
    if volume not in volumes:
        return
    query = (
        "SELECT version_num FROM alembic_version "
        "WHERE to_regclass('public.alembic_version') IS NOT NULL"
    )
    script = 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq -c "$1"'
    # 有資料卻連不上資料庫時讓它失敗: 主機的狀態不是預期的, 不能當成「沒有版本」放行。
    result = docker_exec(env, "postgres", ["sh", "-c", script, "sh", query], capture=True)
    print(result.stdout.strip())


def run(_name: str, args: list[str]) -> None:
    env = load_env()
    require_env(env, "COMPOSE_PROJECT_NAME")
    action, rest = (args[0], args[1:]) if args else ("", [])

    if action == "psql" and not rest:
        script = 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
        docker_exec(env, "postgres", ["sh", "-c", script], interactive=True, check=False)
    elif action == "superuser" and not rest:
        confirm("將建立一個擁有全部權限的超級管理者帳號，確定要繼續？")
        app_cli(env, "superuser", interactive=True)
    elif action == "revoke-sessions" and not rest:
        confirm("所有使用者都會被登出、必須重新登入，確定？")
        app_cli(env, "revoke-sessions")
    elif action == "migration" and len(rest) == 1:
        deny_on_production(env, "make db migration")
        # 與目前的開發資料庫比對, 所以資料庫要先在最新的結構上 (make start 會做)。
        app_cli(env, "migration", rest[0])
        print(MIGRATION_REMINDER)
    elif action == "reset" and not rest:
        deny_on_production(env, "make db reset")
        confirm("資料庫的資料將被清空並重建初始資料，確定？")
        app_cli(env, "reset")
        app_cli(env, "migrate")
    elif action == "revision" and not rest:
        print_revision(env)
    else:
        fail(USAGE)
