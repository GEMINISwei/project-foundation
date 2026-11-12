"""管理指令, 在 api 容器裡執行 (由 make 的各個指令呼叫): python -m app.cli <指令>

migrate                 升到最新的資料庫結構, 再寫入初始資料 (migrate 服務用它)
migration <說明>        依 model 的變動產生一支 migration (僅開發環境)
check-migrations        確認 model 與 migration 一致
reset                   清空資料庫 (僅開發環境)
superuser               建立超級管理者 (互動輸入, 或從 stdin 依序讀暱稱、帳號、密碼)
revoke-sessions         讓所有人都要重新登入
jobs list [狀態]        列出最近的任務 (pending、running、succeeded、failed)
jobs retry <id>         重新排入一個失敗的任務
jobs run <任務名稱>     立刻排入一個任務 (手動觸發排程的任務)
openapi                 把 OpenAPI 契約印到 stdout
"""

import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import NoReturn

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import select, text

from app.registry import ENABLED_MODULES
from shared.db.session import db, engine, start_engine, stop_engine
from shared.errors import AppError
from shared.jobs import enqueue
from shared.jobs.model import Job
from shared.jobs.worker import requeue
from shared.logging import configure_logging
from shared.platform import all_jobs, platform_scope
from shared.settings import settings

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def fail(message: str) -> NoReturn:
    print(f"錯誤：{message}", file=sys.stderr)
    raise SystemExit(1)


def require_development(name: str) -> None:
    if settings.is_production:
        fail(f"{name} 只能在開發環境執行")


def alembic_config() -> Config:
    # 絕對路徑: script_location 是相對 ini 檔算的, 不依賴呼叫時的工作目錄。
    return Config(str(ALEMBIC_INI))


# ── 資料庫 ───────────────────────────────────────────────────────────────────


async def seed() -> None:
    async with platform_scope(ENABLED_MODULES):
        for module in ENABLED_MODULES:
            for seeder in module.seeders:
                await seeder()


def cmd_migrate(_args: list[str]) -> None:
    """資料表與初始資料唯一的寫入路徑; api 開機時不寫任何東西。

    兩段不在同一個交易裡 (alembic 自己管交易): seed 失敗時結構已經升上去, 修好再跑一次即可。
    """
    command.upgrade(alembic_config(), "head")
    asyncio.run(seed())


def cmd_migration(args: list[str]) -> None:
    require_development("migration")
    if len(args) != 1 or not args[0].strip():
        fail('用法：make db migration "說明"')
    command.revision(alembic_config(), message=args[0], autogenerate=True)


def cmd_check_migrations(_args: list[str]) -> None:
    command.check(alembic_config())


async def cmd_reset(_args: list[str]) -> None:
    require_development("reset")
    start_engine()
    try:
        async with engine().begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    finally:
        await stop_engine()
    print("資料庫已清空，執行 make start 重新建立結構")


# ── 帳號 ─────────────────────────────────────────────────────────────────────


def prompt(label: str, *, secret: bool = False) -> str:
    # 有終端機時密碼不回顯; 沒有 (自動化從 stdin 餵) 時逐行讀。密碼不從命令列參數取:
    # 那會留在 shell 歷史與 `ps` 的輸出裡。
    if sys.stdin.isatty():
        value = getpass.getpass(label) if secret else input(label)
    else:
        value = sys.stdin.readline().rstrip("\n")
    return value if secret else value.strip()


async def cmd_superuser(_args: list[str]) -> None:
    from modules.users.public import SuperAdminCreate, create_super_admin

    interactive = sys.stdin.isatty()
    if interactive:
        print("建立超級管理者（此帳號擁有全部權限）")
    nickname = prompt("暱稱：")
    username = prompt("帳號：")
    password = prompt("密碼（至少 8 個字元）：", secret=True)
    if interactive and password != prompt("再次輸入密碼：", secret=True):
        fail("兩次輸入的密碼不一致")
    try:
        data = SuperAdminCreate(username=username, nickname=nickname, password=password)
    except ValidationError as error:
        fail("；".join(f"{item['loc'][0]}: {item['msg']}" for item in error.errors()))
    try:
        async with platform_scope(ENABLED_MODULES):
            user_id = await create_super_admin(data)
    except AppError as error:
        fail(error.spec.text.resolve())
    print(f"已建立超級管理者：{username}（id: {user_id}）")


async def cmd_revoke_sessions(_args: list[str]) -> None:
    from modules.users.public import revoke_all_sessions

    async with platform_scope(ENABLED_MODULES):
        affected = await revoke_all_sessions()
    print(f"已讓 {affected} 位使用者的登入失效，所有人都要重新登入")


# ── 任務 ─────────────────────────────────────────────────────────────────────


async def cmd_jobs(args: list[str]) -> None:
    action, rest = (args[0], args[1:]) if args else ("list", [])
    async with platform_scope(ENABLED_MODULES):
        if action == "list" and len(rest) <= 1:
            statement = select(Job).order_by(Job.created_at.desc()).limit(50)
            if rest:
                statement = statement.where(Job.status == rest[0])
            jobs = (await db().scalars(statement)).all()
            print(f"{'id':<36}  {'狀態':<9}  {'次數':<5}  {'預定執行 (UTC)':<19}  任務")
            for job in jobs:
                tries = f"{job.attempts}/{job.max_attempts}"
                print(
                    f"{job.id}  {job.status:<10} {tries:<6} "
                    f"{job.run_at:%Y-%m-%d %H:%M:%S}  {job.name}"
                )
                if job.last_error:
                    print(f"    └ {job.last_error.strip().splitlines()[-1]}")
        elif action == "retry" and len(rest) == 1:
            if not await requeue(rest[0]):
                fail("找不到這個 id 的失敗任務")
            print("已重新排入")
        elif action == "run" and len(rest) == 1:
            specs = {spec.name: spec for spec in all_jobs(ENABLED_MODULES)}
            if rest[0] not in specs:
                fail("沒有這個任務；可用的任務：" + "、".join(sorted(specs)))
            job = await enqueue(specs[rest[0]])
            print(f"已排入：{job.id}")
        else:
            fail("用法：jobs list [狀態]｜jobs retry <id>｜jobs run <任務名稱>")


# ── 契約 ─────────────────────────────────────────────────────────────────────


def cmd_openapi(_args: list[str]) -> None:
    from app.server import create_app

    # 契約不隨執行環境變: 固定用完整的啟用清單, 鍵值排序讓 diff 穩定。
    print(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True))


COMMANDS = {
    "migrate": cmd_migrate,
    "migration": cmd_migration,
    "check-migrations": cmd_check_migrations,
    "reset": cmd_reset,
    "superuser": cmd_superuser,
    "revoke-sessions": cmd_revoke_sessions,
    "jobs": cmd_jobs,
    "openapi": cmd_openapi,
}


def main(argv: list[str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        raise SystemExit(1)
    if argv[0] != "openapi":
        configure_logging(json_output=settings.is_production)
    result = COMMANDS[argv[0]](argv[1:])
    if asyncio.iscoroutine(result):
        asyncio.run(result)


if __name__ == "__main__":
    main(sys.argv[1:])
