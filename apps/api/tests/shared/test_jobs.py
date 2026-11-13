"""背景任務: 排入、執行、重試、回收, 以及排程不重複也不回補。"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update

from app.registry import ENABLED_MODULES
from shared.db.session import db, independent_session
from shared.jobs import JobSpec, Schedule, current_job_id, enqueue
from shared.jobs import worker as worker_module
from shared.jobs.model import Job, JobStatus, ScheduleState
from shared.jobs.worker import Worker, requeue, retry_delay
from shared.platform import event_bus, unit_of_work

pytestmark = pytest.mark.integration

BUS = event_bus(ENABLED_MODULES)
calls: list[dict[str, Any]] = []


async def record(payload: dict[str, Any]) -> None:
    calls.append(payload)


async def explode(_payload: dict[str, Any]) -> None:
    raise RuntimeError("boom")


async def write_then_explode(_payload: dict[str, Any]) -> None:
    db().add(ScheduleState(name="written-by-job", last_fire_at=datetime.now(UTC)))
    await db().flush()
    raise RuntimeError("boom")


async def write_then_lose_the_job(_payload: dict[str, Any]) -> None:
    db().add(ScheduleState(name="written-by-job", last_fire_at=datetime.now(UTC)))
    await db().flush()
    # 模擬這個 worker 被當成消失: 任務在執行途中被回收, 換別的 worker 接手。
    async with independent_session() as session:
        await session.execute(update(Job).values(locked_by="another-worker"))


async def record_job_id_then_fail_once(_payload: dict[str, Any]) -> None:
    calls.append({"job_id": current_job_id()})
    if len(calls) == 1:
        raise RuntimeError("boom")


RECORD = JobSpec("test.record", record)
TAKEN_OVER = JobSpec("test.taken_over", write_then_lose_the_job)
JOB_ID = JobSpec("test.job_id", record_job_id_then_fail_once)
EXPLODE = JobSpec("test.explode", explode, max_attempts=2)
WRITE = JobSpec("test.write", write_then_explode, max_attempts=1)


def worker(*specs: JobSpec, schedules: tuple[Schedule, ...] = ()) -> Worker:
    return Worker(specs, schedules, BUS)


async def add(spec: JobSpec, payload: dict[str, Any] | None = None, **kwargs: Any) -> Job:
    async with unit_of_work(BUS):
        return await enqueue(spec, payload, **kwargs)


async def reload(job: Job) -> Job:
    async with independent_session() as session:
        found = await session.get(Job, job.id)
        assert found is not None
        return found


@pytest.fixture(autouse=True)
def clear_calls():
    calls.clear()


def test_retry_delay_doubles_up_to_one_hour():
    assert [retry_delay(n).total_seconds() for n in (1, 2, 3)] == [30, 60, 120]
    assert retry_delay(20).total_seconds() == 3600


async def test_a_due_job_runs_once_and_is_marked_succeeded(db_ready):
    job = await add(RECORD, {"n": 1})
    runner = worker(RECORD)
    assert await runner.run_next() is True
    assert await runner.run_next() is False
    assert calls == [{"n": 1}]
    done = await reload(job)
    assert (done.status, done.attempts) == (JobStatus.SUCCEEDED, 1)
    assert done.finished_at is not None


async def test_a_job_scheduled_for_later_is_left_alone(db_ready):
    await add(RECORD, run_at=datetime.now(UTC) + timedelta(hours=1))
    assert await worker(RECORD).run_next() is False


async def test_enqueue_is_rolled_back_with_the_surrounding_transaction(db_ready):
    with pytest.raises(RuntimeError):
        async with unit_of_work(BUS):
            await enqueue(RECORD)
            raise RuntimeError("business failure")
    assert await worker(RECORD).run_next() is False


async def test_a_failing_job_is_retried_later_then_marked_failed(db_ready):
    job = await add(EXPLODE)
    runner = worker(EXPLODE)

    await runner.run_next()
    first = await reload(job)
    assert (first.status, first.attempts) == (JobStatus.PENDING, 1)
    assert first.run_at > datetime.now(UTC)
    assert "boom" in (first.last_error or "")

    async with independent_session() as session:
        await session.execute(update(Job).values(run_at=datetime.now(UTC)))
    await runner.run_next()
    final = await reload(job)
    assert (final.status, final.attempts) == (JobStatus.FAILED, 2)


async def test_writes_of_a_failed_job_are_rolled_back(db_ready):
    await add(WRITE)
    await worker(WRITE).run_next()
    async with independent_session() as session:
        assert await session.get(ScheduleState, "written-by-job") is None


async def test_a_job_and_its_writes_are_committed_together_or_not_at_all(db_ready):
    job = await add(TAKEN_OVER)
    await worker(TAKEN_OVER).run_next()
    async with independent_session() as session:
        assert await session.get(ScheduleState, "written-by-job") is None
    # 接手的 worker 還在跑: 這邊不能把它標成完成, 也不能蓋掉它的狀態。
    untouched = await reload(job)
    assert (untouched.status, untouched.locked_by) == (JobStatus.RUNNING, "another-worker")


async def test_the_job_id_a_handler_sees_is_the_same_on_every_retry(db_ready):
    job = await add(JOB_ID)
    runner = worker(JOB_ID)
    await runner.run_next()
    async with independent_session() as session:
        await session.execute(update(Job).values(run_at=datetime.now(UTC)))
    await runner.run_next()
    assert calls == [{"job_id": job.id}, {"job_id": job.id}]
    assert (await reload(job)).status == JobStatus.SUCCEEDED


async def test_a_job_without_a_handler_fails_immediately(db_ready):
    job = await add(RECORD)
    await worker().run_next()
    failed = await reload(job)
    assert failed.status == JobStatus.FAILED
    assert "test.record" in (failed.last_error or "")


async def test_failed_jobs_can_be_requeued(db_ready):
    job = await add(RECORD)
    await worker().run_next()
    assert await requeue(str(job.id)) is True
    assert await requeue(str(job.id)) is False  # 已經不是失敗的狀態了
    await worker(RECORD).run_next()
    assert (await reload(job)).status == JobStatus.SUCCEEDED


async def test_two_workers_never_take_the_same_job(db_ready):
    await add(RECORD)
    first, second = worker(RECORD), worker(RECORD)
    claimed = [await first.claim(), await second.claim()]
    assert sum(job is not None for job in claimed) == 1


async def test_jobs_of_a_vanished_worker_are_recovered(db_ready):
    job = await add(RECORD)
    runner = worker(RECORD)
    await runner.claim()
    # 模擬 worker 在執行中消失: 鎖定時間早就超過任務的時間上限。
    async with independent_session() as session:
        await session.execute(update(Job).values(locked_at=datetime.now(UTC) - timedelta(hours=1)))
    await runner.recover_stale_jobs()
    recovered = await reload(job)
    assert recovered.status == JobStatus.PENDING
    assert recovered.locked_by is None


async def test_a_new_schedule_does_not_backfill_past_runs(db_ready):
    runner = worker(RECORD, schedules=(Schedule(RECORD, cron="* * * * *"),))
    await runner.enqueue_due_schedules()
    assert await runner.run_next() is False


async def test_a_due_schedule_fires_once_even_with_several_workers(db_ready):
    schedule = Schedule(RECORD, cron="* * * * *", payload={"from": "schedule"})
    first = worker(RECORD, schedules=(schedule,))
    second = worker(RECORD, schedules=(schedule,))
    await first.enqueue_due_schedules()
    # 把「上次觸發」往回撥, 等同於 worker 停機了一陣子、錯過好幾次。
    async with independent_session() as session:
        await session.execute(
            update(ScheduleState).values(last_fire_at=datetime.now(UTC) - timedelta(hours=3))
        )
    await first.enqueue_due_schedules()
    await second.enqueue_due_schedules()
    async with independent_session() as session:
        jobs = (await session.scalars(select(Job))).all()
    # 錯過很多次也只補跑最近的一次。
    assert [job.payload for job in jobs] == [{"from": "schedule"}]
    assert jobs[0].origin == "schedule:* * * * *"


async def test_the_heartbeat_file_is_only_written_while_the_database_is_reachable(
    db_ready, tmp_path, monkeypatch
):
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker_module, "HEARTBEAT_FILE", heartbeat)

    async def beat_once() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(worker(RECORD).heartbeat(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await task

    def unreachable() -> None:
        raise OSError("database is down")

    with monkeypatch.context() as patch:
        patch.setattr(worker_module, "engine", unreachable)
        await beat_once()
    assert not heartbeat.exists()

    await beat_once()
    assert heartbeat.exists()


def test_an_invalid_cron_expression_is_rejected_at_startup():
    with pytest.raises(RuntimeError, match="cron"):
        worker(RECORD, schedules=(Schedule(RECORD, cron="not a cron"),))


def test_job_timeout_over_grace_period_is_refused():
    # 部署時 worker 最多等 330 秒: 上限超過 300 秒的任務會在完成之前被強制終止。
    slow = JobSpec("tests.slow", record, timeout_seconds=301)
    with pytest.raises(RuntimeError, match=r"tests\.slow"):
        Worker((slow,), (), BUS)


async def test_cron_is_read_in_the_configured_timezone(db_ready):
    runner = worker(RECORD, schedules=())
    # 設定的時區是 Asia/Taipei (UTC+8): 每天 03:00 是 UTC 的前一天 19:00。
    now = datetime(2026, 11, 11, 20, 0, tzinfo=UTC)
    fire = runner.last_fire_time(Schedule(RECORD, cron="0 3 * * *"), now)
    assert fire == datetime(2026, 11, 11, 19, 0, tzinfo=UTC)
