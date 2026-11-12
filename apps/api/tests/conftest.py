"""測試的共同設定。

分兩種: 不需要資料庫的直接跑; 標了 `pytest.mark.integration` 的連真的 PostgreSQL
(`make check integration` 會起一個拋棄式的)。integration 測試之間以清空資料表隔離, 所以不平行跑。
"""

import asyncio
import os
from collections.abc import AsyncIterator

# 設定在 import 應用程式之前就要存在。
os.environ.setdefault("PROJECT_NAME", "test")
os.environ.setdefault("MODE", "development")
os.environ.setdefault("POSTGRES_URL", "postgresql+asyncpg://app:app@127.0.0.1:5432/app")
os.environ.setdefault("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("EXPIRE_HOURS", "1")

import httpx2
import pytest
from alembic import command
from sqlalchemy import text

from app.cli import alembic_config
from app.registry import ENABLED_MODULES
from app.server import app
from shared.auth import passwords
from shared.db.base import Base
from shared.db.session import engine, start_engine, stop_engine
from shared.platform import event_bus, unit_of_work


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    # 正式的成本一次約 0.2 秒, 測試裡每建立一個帳號都要付一次。
    monkeypatch.setattr(passwords, "ROUNDS", 4)


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[None]:
    """把測試資料庫升到最新的結構 (走真的 migration), 並啟動這個行程的引擎。"""
    # alembic 自己開事件迴圈, 不能在已經在跑的迴圈裡直接呼叫。
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    start_engine()
    yield
    await stop_engine()


@pytest.fixture
async def db_ready(database: None) -> None:
    """每個測試從乾淨的資料開始: 清空所有資料表, 再寫入初始資料 (系統角色)。"""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine().begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    async with unit_of_work(event_bus(ENABLED_MODULES)):
        for module in ENABLED_MODULES:
            for seeder in module.seeders:
                await seeder()


@pytest.fixture
async def client(db_ready: None) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
