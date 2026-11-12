from typing import Any

import pytest
from fastapi import APIRouter

from shared.jobs import JobSpec, Schedule
from shared.module import ModuleManifest, validate_modules


async def handler(_payload: dict[str, Any]) -> None:
    return None


async def loader(_user_id):
    return None


JOB = JobSpec("a.job", handler)


@pytest.mark.parametrize(
    ("modules", "message"),
    [
        ((ModuleManifest("a"), ModuleManifest("a")), "模組重複"),
        (
            (
                ModuleManifest("a", routers=(APIRouter(prefix="/x"),)),
                ModuleManifest("b", routers=(APIRouter(prefix="/x"),)),
            ),
            "路由前綴重複",
        ),
        ((ModuleManifest("a", jobs=(JOB,)), ModuleManifest("b", jobs=(JOB,))), "任務重複"),
        ((ModuleManifest("a", schedules=(Schedule(JOB, cron="* * * * *"),)),), "沒有登記在 jobs"),
        (
            (
                ModuleManifest("a", identity_loader=loader),
                ModuleManifest("b", identity_loader=loader),
            ),
            "只能有一個模組",
        ),
    ],
)
def test_conflicting_manifests_are_rejected_at_startup(modules, message):
    with pytest.raises(RuntimeError, match=message):
        validate_modules(modules)


def test_valid_manifests_pass_through_unchanged():
    modules = (ModuleManifest("a", jobs=(JOB,), schedules=(Schedule(JOB, cron="0 3 * * *"),)),)
    assert validate_modules(modules) == modules
