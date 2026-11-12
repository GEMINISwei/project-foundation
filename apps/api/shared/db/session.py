"""引擎與「目前這段工作用哪個 session」。

一次請求 (或一個任務、一次 CLI 指令) 是一個工作單元: 一個 session、一個交易, 結束時整批
commit 或 rollback。session 放在 ContextVar, repository 用 `db()` 取得, 不必逐層傳參數。

沒有任何一層會自動開 session: 不在 `session_scope()` 裡呼叫 `db()` 直接丟錯, 否則每個操作會
各自成為一個交易, 原子性就悄悄消失了。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.settings import settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None
_current: ContextVar[AsyncSession | None] = ContextVar("db_session", default=None)


def start_engine() -> AsyncEngine:
    """建立這個行程的引擎與連線池。每個行程在啟動時呼叫一次。"""
    global _engine, _factory
    _engine = create_async_engine(
        settings.postgres_url,
        # 資料庫重啟或連線被中途掐斷時, 死連線在取用時就換掉, 不會變成使用者眼前的 500。
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args={
            "server_settings": {"statement_timeout": str(settings.db_statement_timeout_ms)}
        },
    )
    # expire_on_commit=False: commit 之後還要把物件轉成回應, 不該為此再查一次資料庫。
    _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def stop_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = _factory = None


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("資料庫引擎尚未啟動, 請先呼叫 start_engine()")
    return _engine


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """開一個工作單元: 正常結束時 commit, 例外時 rollback。"""
    if _factory is None:
        raise RuntimeError("資料庫引擎尚未啟動, 請先呼叫 start_engine()")
    async with _factory() as session:
        token = _current.set(session)
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
        finally:
            _current.reset(token)


@asynccontextmanager
async def independent_session() -> AsyncIterator[AsyncSession]:
    """與目前工作單元無關的另一個交易, 不會成為「目前的 session」。

    給「不論這次請求成功或失敗都要留下」的寫入用: 限流計數、AUDIT 紀錄。
    """
    if _factory is None:
        raise RuntimeError("資料庫引擎尚未啟動, 請先呼叫 start_engine()")
    async with _factory() as session, session.begin():
        yield session


def db() -> AsyncSession:
    """目前工作單元的 session。"""
    session = _current.get()
    if session is None:
        raise RuntimeError("目前沒有資料庫 session: HTTP 以外的入口要包在 platform_scope() 裡")
    return session


async def release_connection() -> None:
    """結束目前只讀過的交易, 把連線還回連線池; 之後的查詢會自動再拿一條。

    給請求中途要做慢的非資料庫工作 (密碼雜湊) 的路徑用, 那段時間不該佔著連線。
    已經寫過資料就拒絕: 中途結束交易會讓「回應是錯誤就整批回滾」對那些寫入失效。
    """
    session = db()
    if not session.in_transaction():
        return
    if await session.scalar(text("SELECT pg_current_xact_id_if_assigned() IS NOT NULL")):
        raise RuntimeError("這次請求已經寫過資料, 不能中途歸還連線")
    # 只讀過的交易 commit 與 rollback 等價; 用 commit 是因為 rollback 會讓已載入的物件過期,
    # 之後讀它們的欄位就得再查一次資料庫。
    await session.commit()
