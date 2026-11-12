"""所有資料表的共同基底與欄位慣例。

- 主鍵是 UUIDv7: 依時間遞增, 索引不會像 UUIDv4 那樣四散。
- 時間欄位一律帶時區 (`TIMESTAMP WITH TIME ZONE`), 程式裡只用 aware 的 UTC 時間。
- 約束與索引的名稱由 naming convention 決定, migration 才能穩定地指到它們。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


class Entity(Base):
    """有自己識別碼的業務資料: id、建立時間、更新時間。"""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
