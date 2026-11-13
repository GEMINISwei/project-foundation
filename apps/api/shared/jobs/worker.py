"""worker 的執行迴圈: 排入到期的排程、取任務、執行、記錄結果。

- 取任務用 `FOR UPDATE SKIP LOCKED`, 多個 worker 不會拿到同一筆。
- 任務在與 HTTP 請求相同的工作單元裡執行 (交易、事件、AUDIT), 追蹤 id 是 `job-<任務 id>`。
- 「標記完成」與處理函式的寫入在同一個交易: 不會有「資料寫了、任務卻重跑一次」的情況。
- 失敗會重試, 等待時間每次加倍; 用完次數標成 failed, 留著錯誤訊息等人處理 (make jobs retry)。
- worker 中途消失 (被 kill、主機重開) 的任務, 超過時間上限後由其他 worker 回收。
- 停機期間錯過的排程, 恢復後只補跑最近一次; 新加入的排程不回補過去的時間。
"""

import asyncio
import os
import socket
import traceback
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import ColumnElement, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from shared import context
from shared.db.base import utc_now
from shared.db.session import engine, independent_session
from shared.events import EventBus
from shared.jobs import MAX_TIMEOUT_SECONDS, JobSpec, Schedule, running_job
from shared.jobs.model import Job, JobStatus, ScheduleState
from shared.logging import get_logger
from shared.platform import unit_of_work
from shared.settings import settings

log = get_logger(__name__)

SCHEDULE_TICK_SECONDS = 30
RETRY_BASE_SECONDS = 30
RETRY_MAX_SECONDS = 3600
#: 超過任務的時間上限再多等這麼久, 才認定執行它的 worker 已經不在了。
STALE_GRACE_SECONDS = 60
_MAX_ERROR_LENGTH = 4000
#: 容器的 healthcheck 看這個檔案夠不夠新 (infra/compose/compose.yml)。
HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")  # noqa: S108  # 容器裡只有 worker 自己
HEARTBEAT_SECONDS = 15


def retry_delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(RETRY_BASE_SECONDS * 2 ** (attempts - 1), RETRY_MAX_SECONDS))


class Worker:
    def __init__(
        self, jobs: Iterable[JobSpec], schedules: Iterable[Schedule], bus: EventBus
    ) -> None:
        self.specs = {spec.name: spec for spec in jobs}
        self.schedules = tuple(schedules)
        self.bus = bus
        self.name = f"{socket.gethostname()}-{os.getpid()}"
        self.timezone = ZoneInfo(settings.timezone)
        for schedule in self.schedules:
            if not croniter.is_valid(schedule.cron):
                raise RuntimeError(f"排程的 cron 運算式無效: {schedule.name}")
        for spec in self.specs.values():
            if spec.timeout_seconds > MAX_TIMEOUT_SECONDS:
                raise RuntimeError(
                    f"任務的時間上限不能超過 {MAX_TIMEOUT_SECONDS} 秒, 請拆成多個任務: {spec.name}"
                )

    async def run(self, stop: asyncio.Event) -> None:
        log.info(
            "worker_started",
            worker=self.name,
            jobs=sorted(self.specs),
            schedules=[schedule.name for schedule in self.schedules],
        )
        next_schedule_tick = 0.0
        loop = asyncio.get_running_loop()
        while not stop.is_set():
            try:
                if loop.time() >= next_schedule_tick:
                    await self.enqueue_due_schedules()
                    await self.recover_stale_jobs()
                    next_schedule_tick = loop.time() + SCHEDULE_TICK_SECONDS
                if await self.run_next():
                    continue  # 還有任務就接著做, 不等輪詢間隔。
            except Exception:
                # 資料庫暫時連不上之類的: 記下來, 等下一輪再試, worker 不能因此結束。
                log.exception("worker_loop_error")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.job_poll_seconds)
            except TimeoutError:
                pass
        log.info("worker_stopped", worker=self.name)

    async def heartbeat(self, stop: asyncio.Event) -> None:
        """定期確認資料庫連得上並更新心跳檔。與執行迴圈分開: 任務跑很久的時候心跳不能斷。"""
        while not stop.is_set():
            try:
                async with engine().connect() as connection:
                    await connection.execute(text("SELECT 1"))
                await asyncio.to_thread(HEARTBEAT_FILE.touch)
            except Exception:
                log.exception("worker_heartbeat_failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                pass

    # ── 排程 ─────────────────────────────────────────────────────────────────

    def last_fire_time(self, schedule: Schedule, now: datetime) -> datetime:
        """`now` 之前 (含) 最近一次應該觸發的時間。"""
        local = now.astimezone(self.timezone)
        fire: datetime = croniter(schedule.cron, local + timedelta(seconds=1)).get_prev(datetime)
        return fire.astimezone(now.tzinfo)

    async def enqueue_due_schedules(self) -> None:
        now = utc_now()
        for schedule in self.schedules:
            fire = self.last_fire_time(schedule, now)
            async with independent_session() as session:
                # 第一次看到這個排程: 從現在起算, 不回補過去的觸發時間。
                await session.execute(
                    insert(ScheduleState)
                    .values(name=schedule.name, last_fire_at=now)
                    .on_conflict_do_nothing()
                )
                # 同一個觸發時間只有一個 worker 的 UPDATE 會成立, 由它排入任務。
                claimed = await session.scalar(
                    update(ScheduleState)
                    .where(ScheduleState.name == schedule.name, ScheduleState.last_fire_at < fire)
                    .values(last_fire_at=fire)
                    .returning(ScheduleState.name)
                )
                if claimed:
                    session.add(
                        Job(
                            name=schedule.job.name,
                            payload=schedule.payload,
                            max_attempts=schedule.job.max_attempts,
                            timeout_seconds=schedule.job.timeout_seconds,
                            origin=f"schedule:{schedule.cron}",
                        )
                    )
                    log.info("schedule_fired", schedule=schedule.name, fire_at=fire.isoformat())

    # ── 取任務與執行 ─────────────────────────────────────────────────────────

    async def recover_stale_jobs(self) -> None:
        deadline = Job.locked_at + func.make_interval(
            0, 0, 0, 0, 0, 0, Job.timeout_seconds + STALE_GRACE_SECONDS
        )
        async with independent_session() as session:
            stale = (
                await session.scalars(
                    select(Job)
                    .where(Job.status == JobStatus.RUNNING, deadline < func.now())
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for job in stale:
                self._record_failure(job, "執行這個任務的 worker 中途消失")
                log.warning("job_recovered", job_id=str(job.id), job=job.name, status=job.status)

    async def claim(self) -> Job | None:
        candidate = (
            select(Job.id)
            .where(Job.status == JobStatus.PENDING, Job.run_at <= func.now())
            .order_by(Job.run_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        async with independent_session() as session:
            return await session.scalar(
                update(Job)
                .where(Job.id == candidate)
                .values(
                    status=JobStatus.RUNNING,
                    locked_by=self.name,
                    locked_at=func.now(),
                    attempts=Job.attempts + 1,
                )
                .returning(Job)
            )

    async def run_next(self) -> bool:
        """執行一個到期的任務; 沒有任務可做時回傳 False。"""
        job = await self.claim()
        if job is None:
            return False
        context.begin(trace_id=f"job-{job.id.hex[:16]}")
        spec = self.specs.get(job.name)
        started = asyncio.get_running_loop().time()
        error: str | None = None
        try:
            if spec is None:
                # 任務被改名或移除了: 重試也不會好, 直接用完次數。
                job.attempts = job.max_attempts
                raise RuntimeError(f"沒有這個任務的處理函式: {job.name}")
            async with asyncio.timeout(job.timeout_seconds), unit_of_work(self.bus) as session:
                token = running_job.set(job.id)
                try:
                    await spec.handler(job.payload)
                finally:
                    running_job.reset(token)
                finished = await session.execute(
                    update(Job)
                    .where(*self._still_mine(job))
                    .values(status=JobStatus.SUCCEEDED, finished_at=utc_now(), last_error=None)
                )
                if not finished.rowcount:  # type: ignore[attr-defined]  # CursorResult 才有
                    # 丟出去讓交易回滾: 接手的 worker 會把同樣的事再做一次。
                    raise RuntimeError("任務在執行途中被回收, 已經不屬於這個 worker")
        except Exception:
            error = traceback.format_exc()
            log.exception("job_failed", job_id=str(job.id), job=job.name, attempt=job.attempts)
        duration_ms = round((asyncio.get_running_loop().time() - started) * 1000, 1)

        if error is None:
            log.info("job_succeeded", job_id=str(job.id), job=job.name, duration_ms=duration_ms)
            return True
        async with independent_session() as session:
            # 條件不成立有兩種情況, 都不該動它: 任務被別的 worker 接手了, 或是 commit 其實
            # 成功了、例外是之後才發生的。
            current = await session.scalar(
                select(Job).where(*self._still_mine(job)).with_for_update()
            )
            if current is not None:
                current.attempts = job.attempts
                self._record_failure(current, error)
        return True

    def _still_mine(self, job: Job) -> tuple[ColumnElement[bool], ...]:
        return (Job.id == job.id, Job.status == JobStatus.RUNNING, Job.locked_by == self.name)

    @staticmethod
    def _record_failure(job: Job, error: str) -> None:
        job.last_error = error[-_MAX_ERROR_LENGTH:]
        job.locked_by = None
        job.locked_at = None
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.finished_at = utc_now()
        else:
            job.status = JobStatus.PENDING
            job.run_at = utc_now() + retry_delay(job.attempts)


async def requeue(job_id: str) -> bool:
    """把失敗的任務重新排入 (make jobs retry)。回傳有沒有找到可以重排的任務。"""
    async with independent_session() as session:
        result = await session.execute(
            text(
                "UPDATE jobs SET status = 'pending', attempts = 0, run_at = now(), "
                "finished_at = NULL WHERE id = CAST(:id AS uuid) AND status = 'failed'"
            ),
            {"id": job_id},
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]
