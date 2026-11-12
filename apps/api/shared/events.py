"""模組之間的行程內事件。

被參照的模組需要通知參照它的模組時用 (停用使用者時連動取消訂單), 不必反過來 import:
發布者在自己的 `public.py` 定義事件並 `await publish(...)`,
訂閱者在 manifest 的 `event_handlers` 登記。

處理函式在發布者的交易裡同步執行, 丟出錯誤就否決整個操作。寄信、呼叫外部服務這類提交之後才該
發生的副作用, 在處理函式裡排入背景任務 (`shared.jobs.enqueue`)。
"""

from collections.abc import Awaitable, Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


class Event:
    """事件的基底類別, 子類別用 `@dataclass(frozen=True)` 宣告欄位。"""


@dataclass(frozen=True)
class EventHandler:
    event: type[Event]
    handle: Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self, handlers: Iterable[EventHandler]) -> None:
        self._handlers = tuple(handlers)
        for handler in self._handlers:
            # 登記錯型別的話 isinstance 永遠不成立, 處理函式就靜靜地從來不會被呼叫。
            if not (isinstance(handler.event, type) and issubclass(handler.event, Event)):
                raise RuntimeError(f"訂閱的不是事件類別: {handler.event!r}")

    async def dispatch(self, event: Event) -> None:
        for handler in self._handlers:
            if isinstance(event, handler.event):
                await handler.handle(event)


_bus: ContextVar[EventBus | None] = ContextVar("event_bus", default=None)


@contextmanager
def use_event_bus(bus: EventBus) -> Iterator[None]:
    token = _bus.set(bus)
    try:
        yield
    finally:
        _bus.reset(token)


async def publish(event: Event) -> None:
    bus = _bus.get()
    if bus is None:
        raise RuntimeError("目前沒有事件訂閱表: HTTP 以外的入口要包在 platform_scope() 裡")
    await bus.dispatch(event)
