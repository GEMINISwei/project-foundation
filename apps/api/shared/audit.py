"""AUDIT: 安全相關事件的紀錄 (登入失敗的原因、誰改了誰的角色)。

    audit("role_updated", role_id=role.id, permissions=role.permissions)

每筆自動帶上操作者、IP 與 request id, 同時寫進 log 與 `audit_logs` 資料表。資料表的那一份在
這次請求結束後另開交易寫入: 「登入失敗」這類事件的請求本身會回滾, 紀錄不能跟著消失。
所以每筆都帶 `committed`: 這次請求的寫入最後有沒有成立。`role_updated` 配上 `committed = false`
代表有人試過但資料沒有變。

資料表那一份寫入失敗時只留在 log (`audit_flush_failed`), 沒有補寫 (docs/foundation/decisions.md)。

只放 id 與固定的代碼, 不放帳號、暱稱或使用者輸入的內容: 紀錄會長期留存與備份。
"""

import uuid
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared import context
from shared.db.base import Base, utc_now
from shared.db.session import independent_session
from shared.logging import get_logger

log = get_logger(__name__)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_event_created_at", "event", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    event: Mapped[str]
    # 不加外鍵: 紀錄要比它提到的資料活得久。
    actor_id: Mapped[str] = mapped_column(index=True)
    ip: Mapped[str]
    request_id: Mapped[str] = mapped_column(index=True)
    committed: Mapped[bool]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


_pending: ContextVar[list[AuditLog] | None] = ContextVar("audit_pending", default=None)
_discarded: ContextVar[bool] = ContextVar("audit_discarded", default=False)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def audit(event: str, **data: Any) -> None:
    fields = {key: _plain(value) for key, value in data.items() if value is not None}
    # 欄位收在 data 底下: 事件的 user_id (對象) 才不會蓋掉 log 情境裡的 user_id (操作者)。
    log.info("audit", audit_event=event, ip=context.client_ip.get(), data=fields)
    pending = _pending.get()
    if pending is not None:
        pending.append(
            AuditLog(
                event=event,
                actor_id=context.user_id.get(),
                ip=context.client_ip.get(),
                request_id=context.request_id.get(),
                data=fields,
            )
        )


def begin_collecting() -> None:
    _pending.set([])
    _discarded.set(False)


def mark_rolled_back() -> None:
    """工作單元沒有丟例外、但主動放棄了寫入 (回應是 4xx) 時呼叫。"""
    _discarded.set(True)


async def flush(*, committed: bool) -> None:
    """把這次請求累積的紀錄寫進資料表。寫入失敗只記 log, 不影響已經完成的請求。"""
    pending = _pending.get()
    _pending.set(None)
    if not pending:
        return
    committed = committed and not _discarded.get()
    for entry in pending:
        entry.committed = committed
    if not committed:
        # log 那一份在事件當下就寫了, 當時還不知道結果: 補一行才能只靠 log 還原。
        log.info("audit_rolled_back", events=[entry.event for entry in pending])
    try:
        async with independent_session() as session:
            session.add_all(pending)
    except Exception:
        log.exception("audit_flush_failed", count=len(pending))
