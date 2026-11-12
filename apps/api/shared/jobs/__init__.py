"""背景任務: 定義、排入與排程。

模組在 manifest 宣告任務與排程:

    async def send_report(payload: dict[str, Any]) -> None: ...

    SEND_REPORT = JobSpec("reports.send", send_report)
    MODULE = ModuleManifest(
        ...,
        jobs=(SEND_REPORT,),
        schedules=(Schedule(SEND_REPORT, cron="0 3 * * *"),),   # 每天 03:00 (TIMEZONE 設定的時區)
    )

需要時主動排入: `await enqueue(SEND_REPORT, {"report_id": str(report.id)})`。排入與業務資料在同一個
交易裡, 資料沒寫成功任務也不會存在。

任務會重試, 所以處理函式必須能重跑: 同一筆 payload 執行兩次的結果要與執行一次相同。

- 寫進資料庫的部分不必自己處理: 任務標記完成與處理函式的寫入在同一個交易, 不會只成立一半。
- 資料庫以外的副作用 (寄信、扣款、呼叫外部 API) 交易管不到, 可能重複: 把 `current_job_id()`
  當成去重的鍵交給對方 (idempotency key), 它在每次重試都相同。
"""

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared import context
from shared.db.session import db
from shared.jobs.model import Job

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]

running_job: ContextVar[uuid.UUID | None] = ContextVar("running_job", default=None)


def current_job_id() -> uuid.UUID:
    """正在執行的任務的 id。只能在任務的處理函式裡呼叫。"""
    job_id = running_job.get()
    if job_id is None:
        raise RuntimeError("目前不在任務的處理函式裡")
    return job_id


@dataclass(frozen=True)
class JobSpec:
    #: 全系統唯一, 慣例是 `<模組>.<動作>`。改名會讓已經排入的舊任務找不到處理函式。
    name: str
    handler: JobHandler
    #: 含第一次在內最多執行幾次; 每次失敗後等待的時間加倍 (30 秒起, 上限 1 小時)。
    max_attempts: int = 3
    #: 單次執行的時間上限。要小於 worker 的 stop_grace_period (330 秒)。
    timeout_seconds: int = 300


@dataclass(frozen=True)
class Schedule:
    job: JobSpec
    #: 標準的五欄 cron 運算式, 以 TIMEZONE 設定的時區解讀。
    cron: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.job.name}@{self.cron}"


async def enqueue(
    spec: JobSpec, payload: dict[str, Any] | None = None, *, run_at: datetime | None = None
) -> Job:
    """把任務排進佇列, 與目前的交易一起提交。`run_at` 不給就是盡快執行。"""
    job = Job(
        name=spec.name,
        payload=payload or {},
        max_attempts=spec.max_attempts,
        timeout_seconds=spec.timeout_seconds,
        origin=context.request_id.get(),
    )
    if run_at is not None:
        job.run_at = run_at
    db().add(job)
    await db().flush()
    return job
