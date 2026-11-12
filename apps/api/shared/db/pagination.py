"""游標 (keyset) 分頁。

排序鍵是 `(created_at, id)`: 只用 created_at 的話, 時間相同的兩筆在兩次查詢間順序不保證,
翻頁會跳過或重複。篩選條件 (`where`) 同時套用在資料與總數上; 游標條件不進總數。
"""

import base64
import binascii
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.sql.base import ExecutableOption

from shared.db.base import Entity
from shared.db.session import db
from shared.errors import INVALID_CURSOR


class PageParams(BaseModel):
    """列表端點共用的分頁參數, 搭配 `Annotated[PageParams, Query()]`。篩選條件由各路由自己宣告。"""

    cursor: str | None = None
    direction: Literal["next", "prev"] = "next"
    limit: int = Field(default=20, ge=1, le=100)


class Page[T](BaseModel):
    """游標分頁列表的回應。"""

    items: list[T]
    total: int
    next_cursor: str | None
    prev_cursor: str | None


class ItemList[T](BaseModel):
    """不分頁的完整清單 (下拉選單用)。"""

    items: list[T]


@dataclass(frozen=True)
class PageResult[M]:
    items: list[M]
    total: int
    next_cursor: str | None
    prev_cursor: str | None

    def to_page[T](self, items: list[T]) -> Page[T]:
        return Page(
            items=items,
            total=self.total,
            next_cursor=self.next_cursor,
            prev_cursor=self.prev_cursor,
        )


def _encode(row: Entity) -> str:
    raw = json.dumps([row.created_at.isoformat(), str(row.id)])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_at, row_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(created_at), uuid.UUID(row_id)
    except (ValueError, TypeError, binascii.Error) as error:
        raise INVALID_CURSOR() from error


def _beyond(column: Any, value: Any, backward: bool) -> ColumnElement[bool]:
    """沿著翻頁方向, 欄位值在游標之後。"""
    result: ColumnElement[bool] = column < value if backward else column > value
    return result


async def paginate[M: Entity](
    model: type[M],
    params: PageParams,
    *,
    where: Sequence[ColumnElement[bool]] = (),
    options: Sequence[ExecutableOption] = (),
) -> PageResult[M]:
    """依建立時間由舊到新分頁。`options` 放關聯的載入方式 (selectinload), 不影響筆數。"""
    backward = params.direction == "prev"
    conditions = list(where)
    if params.cursor is not None:
        created_at, row_id = _decode(params.cursor)
        conditions.append(
            or_(
                _beyond(model.created_at, created_at, backward),
                and_(model.created_at == created_at, _beyond(model.id, row_id, backward)),
            )
        )
    ordering = (
        (model.created_at.desc(), model.id.desc())
        if backward
        else (model.created_at.asc(), model.id.asc())
    )
    statement = (
        select(model)
        .where(*conditions)
        .options(*options)
        .order_by(*ordering)
        .limit(params.limit + 1)
    )
    rows = list((await db().scalars(statement)).all())
    more = len(rows) > params.limit
    rows = rows[: params.limit]
    if backward:
        rows.reverse()

    # 沿著翻頁方向還有沒有下一批看 `more`; 反方向只要帶了游標就一定有 (剛從那邊翻過來)。
    has_next = more if not backward else True
    has_previous = more if backward else params.cursor is not None

    total = await db().scalar(select(func.count()).select_from(model).where(*where)) or 0
    return PageResult(
        items=rows,
        total=total,
        next_cursor=_encode(rows[-1]) if rows and has_next else None,
        prev_cursor=_encode(rows[0]) if rows and has_previous else None,
    )
