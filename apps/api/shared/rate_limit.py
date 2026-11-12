"""限流。計數放在 PostgreSQL, api 開多個行程或副本時共用同一份。

    login_limiter = RateLimiter("login", max_attempts=10, window_seconds=300)
    await login_limiter.check(f"{ip}:{username}")

固定時間窗: 每個 key 在每個窗口內最多 `max_attempts` 次。計數另開交易寫入, 所以被拒絕或失敗的
請求也算數。過期的計數由內建的排程任務清理。
"""

import hashlib
import math
import time
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.db.session import independent_session
from shared.errors import ErrorSpec
from shared.i18n import LangText

RATE_LIMITED = ErrorSpec(
    429,
    "rate_limit.exceeded",
    LangText(zh="嘗試次數過多，請稍後再試", en="Too many attempts, please try again later"),
)


class RateLimitCount(Base):
    __tablename__ = "rate_limits"

    key: Mapped[str] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(primary_key=True)
    count: Mapped[int]


class RateLimiter:
    def __init__(self, name: str, *, max_attempts: int, window_seconds: int) -> None:
        self.name = name
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def _key(self, key: str) -> str:
        # key 可能含使用者輸入的帳號: 存雜湊, 長度固定, 資料表裡也不留原文。
        return f"{self.name}:{hashlib.sha256(key.encode()).hexdigest()}"

    async def check(self, key: str) -> None:
        """記一次嘗試; 超過上限就丟 429 (帶 Retry-After)。"""
        now = time.time()
        window = math.floor(now / self.window_seconds) * self.window_seconds
        statement = (
            insert(RateLimitCount)
            .values(key=self._key(key), window_start=datetime.fromtimestamp(window, UTC), count=1)
            .on_conflict_do_update(
                index_elements=["key", "window_start"],
                set_={"count": RateLimitCount.count + 1},
            )
            .returning(RateLimitCount.count)
        )
        async with independent_session() as session:
            count = await session.scalar(statement)
        if count is not None and count > self.max_attempts:
            retry_after = max(1, math.ceil(window + self.window_seconds - now))
            raise RATE_LIMITED(headers={"Retry-After": str(retry_after)})

    async def reset(self, key: str) -> None:
        """清掉這個 key 的計數 (例如登入成功之後)。"""
        async with independent_session() as session:
            await session.execute(
                delete(RateLimitCount).where(RateLimitCount.key == self._key(key))
            )
