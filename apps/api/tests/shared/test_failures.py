"""出錯時的行為: 沒被處理的例外、外鍵違反, 以及平台內建的清理任務。"""

from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.permissions import Permission
from app.registry import ENABLED_MODULES
from shared.db.integrity import foreign_key_error, is_unique_violation
from shared.db.session import db, independent_session
from shared.errors import REFERENCE_NOT_FOUND, STILL_REFERENCED
from shared.jobs.builtin import cleanup_jobs, cleanup_rate_limits
from shared.jobs.model import Job, JobStatus, ScheduleState
from shared.module import ModuleManifest
from shared.platform import create_platform_app, event_bus, unit_of_work
from shared.rate_limit import RateLimitCount

router = APIRouter(prefix="/broken")


@router.post("/write-then-crash")
async def write_then_crash() -> None:
    db().add(ScheduleState(name="half-written", last_fire_at=datetime.now(UTC)))
    await db().flush()
    raise RuntimeError("unexpected")


broken_app = create_platform_app(
    modules=(*ENABLED_MODULES, ModuleManifest("broken", routers=(router,))),
    permissions=Permission,
    app_version="test",
)


class FakeDriverError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("uq_roles_name")
        self.sqlstate = sqlstate


def integrity(sqlstate: str, statement: str) -> IntegrityError:
    return IntegrityError(statement, {}, FakeDriverError(sqlstate))


def test_foreign_key_violations_are_told_apart_by_the_statement():
    assert foreign_key_error(integrity("23503", "DELETE FROM roles")) is STILL_REFERENCED
    assert foreign_key_error(integrity("23503", "INSERT INTO user_roles")) is REFERENCE_NOT_FOUND
    assert foreign_key_error(integrity("23505", "INSERT INTO roles")) is None


def test_unique_violations_can_be_matched_to_one_constraint():
    error = integrity("23505", "INSERT INTO roles")
    assert is_unique_violation(error)
    assert is_unique_violation(error, "uq_roles_name")
    assert not is_unique_violation(error, "uq_users_username")
    assert not is_unique_violation(integrity("23503", "INSERT"))


@pytest.mark.integration
async def test_an_unhandled_error_becomes_a_500_and_rolls_everything_back(db_ready):
    transport = httpx2.ASGITransport(app=broken_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/broken/write-then-crash")
    body = response.json()
    assert (response.status_code, body["code"]) == (500, "internal")
    # 不把內部的錯誤訊息交給用戶端, 只給追蹤 id。
    assert "unexpected" not in response.text
    assert body["request_id"] == response.headers["x-request-id"]
    async with independent_session() as session:
        assert await session.get(ScheduleState, "half-written") is None


@pytest.mark.integration
async def test_builtin_cleanup_removes_only_what_is_past_retention(db_ready):
    now = datetime.now(UTC)

    def job(status: JobStatus, days_ago: int) -> Job:
        return Job(
            name="x",
            status=status,
            max_attempts=1,
            timeout_seconds=1,
            finished_at=now - timedelta(days=days_ago),
        )

    async with independent_session() as session:
        session.add_all(
            [
                job(JobStatus.SUCCEEDED, 1),
                job(JobStatus.SUCCEEDED, 30),
                job(JobStatus.FAILED, 30),
                job(JobStatus.FAILED, 120),
                RateLimitCount(key="old", window_start=now - timedelta(days=3), count=1),
                RateLimitCount(key="new", window_start=now, count=1),
            ]
        )
    async with unit_of_work(event_bus(ENABLED_MODULES)):
        await cleanup_jobs({})
        await cleanup_rate_limits({})
    async with independent_session() as session:
        jobs = (await session.scalars(select(Job))).all()
        limits = (await session.scalars(select(RateLimitCount.key))).all()
    assert sorted((j.status, (now - j.finished_at).days) for j in jobs if j.finished_at) == [
        ("failed", 30),
        ("succeeded", 1),
    ]
    assert limits == ["new"]
