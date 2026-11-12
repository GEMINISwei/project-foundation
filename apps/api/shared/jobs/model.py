"""背景任務與排程的資料表。"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base, Entity, utc_now


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(Entity):
    __tablename__ = "jobs"
    __table_args__ = (
        # worker 每幾秒查一次的就是這個條件, 索引只收待執行的那幾筆。
        Index("ix_jobs_pending_run_at", "run_at", postgresql_where=text("status = 'pending'")),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

    name: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(default=JobStatus.PENDING)
    run_at: Mapped[datetime] = mapped_column(default=utc_now)
    attempts: Mapped[int] = mapped_column(default=0)
    # 排入當下從 JobSpec 抄一份: 回收卡住的任務時只靠這一列就能判斷, 不必認得所有任務定義。
    max_attempts: Mapped[int]
    timeout_seconds: Mapped[int]
    locked_by: Mapped[str | None]
    locked_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    # 排入這個任務的請求 (或排程), 追查時從任務接回當初的操作。
    origin: Mapped[str] = mapped_column(default="-")


class ScheduleState(Base):
    """每個排程最後一次已經排入任務的觸發時間, 多個 worker 靠它不重複排入。"""

    __tablename__ = "job_schedules"

    name: Mapped[str] = mapped_column(primary_key=True)
    last_fire_at: Mapped[datetime]
