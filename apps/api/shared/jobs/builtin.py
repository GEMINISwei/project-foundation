"""平台內建的排程: 清理平台自己的資料表。不論啟用哪些模組都會執行。"""

from datetime import timedelta
from typing import Any

from sqlalchemy import delete

from shared.db.base import utc_now
from shared.db.session import db
from shared.jobs import JobSpec, Schedule
from shared.jobs.model import Job, JobStatus
from shared.logging import get_logger
from shared.rate_limit import RateLimitCount

log = get_logger(__name__)

#: 成功的任務紀錄只為了確認「有跑」, 失敗的要留久一點供追查。
SUCCEEDED_RETENTION = timedelta(days=14)
FAILED_RETENTION = timedelta(days=90)
#: 遠大於任何限流窗口即可。
RATE_LIMIT_RETENTION = timedelta(days=1)


async def cleanup_jobs(_payload: dict[str, Any]) -> None:
    now = utc_now()
    removed = 0
    for status, retention in (
        (JobStatus.SUCCEEDED, SUCCEEDED_RETENTION),
        (JobStatus.FAILED, FAILED_RETENTION),
    ):
        result = await db().execute(
            delete(Job).where(Job.status == status, Job.finished_at < now - retention)
        )
        removed += result.rowcount or 0  # type: ignore[attr-defined]
    log.info("jobs_cleaned", removed=removed)


async def cleanup_rate_limits(_payload: dict[str, Any]) -> None:
    result = await db().execute(
        delete(RateLimitCount).where(RateLimitCount.window_start < utc_now() - RATE_LIMIT_RETENTION)
    )
    log.info("rate_limits_cleaned", removed=result.rowcount or 0)  # type: ignore[attr-defined]


CLEANUP_JOBS = JobSpec("platform.cleanup_jobs", cleanup_jobs)
CLEANUP_RATE_LIMITS = JobSpec("platform.cleanup_rate_limits", cleanup_rate_limits)

BUILTIN_JOBS = (CLEANUP_JOBS, CLEANUP_RATE_LIMITS)
BUILTIN_SCHEDULES = (
    Schedule(CLEANUP_JOBS, cron="30 3 * * *"),
    Schedule(CLEANUP_RATE_LIMITS, cron="15 * * * *"),
)
