"""資料庫完整性錯誤的判讀。

比對 SQLSTATE 而不是訊息字串: 訊息會隨 PostgreSQL 的語系改變。
"""

from sqlalchemy.exc import IntegrityError

from shared.errors import REFERENCE_NOT_FOUND, STILL_REFERENCED, ErrorSpec

_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"


def _sqlstate(error: IntegrityError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def is_unique_violation(error: IntegrityError, constraint: str | None = None) -> bool:
    """是不是撞到唯一約束; 給了 `constraint` 就只認那一個 (名稱見 Base 的 naming convention)。"""
    if _sqlstate(error) != _UNIQUE_VIOLATION:
        return False
    return constraint is None or constraint in str(error.orig)


def foreign_key_error(error: IntegrityError) -> ErrorSpec | None:
    """外鍵違反對應的錯誤; 不是外鍵違反時回傳 None。

    刪除時是「仍被參照」, 新增或更新時是「參照的資料不存在」, 依觸發錯誤的 SQL 種類區分。
    """
    if _sqlstate(error) != _FOREIGN_KEY_VIOLATION:
        return None
    statement = (error.statement or "").lstrip().upper()
    return STILL_REFERENCED if statement.startswith("DELETE") else REFERENCE_NOT_FOUND
