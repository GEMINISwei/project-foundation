"""Alembic 的執行環境: 用與應用相同的設定與 model 連線、比對結構。"""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# 載入所有資料表: 啟用中模組的 (經由 registry) 與平台自己的。漏載入的表 autogenerate 會當成要刪除。
import app.registry
import shared.audit
import shared.jobs.model
import shared.rate_limit
from shared.db.base import Base
from shared.settings import settings

target_metadata = Base.metadata


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # 欄位型別與預設值的變動也要偵測, 否則 model 改了型別卻產不出 migration。
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async() -> None:
    engine = create_async_engine(settings.postgres_url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("不支援離線模式: migration 一律連上資料庫執行")

asyncio.run(run_async())
