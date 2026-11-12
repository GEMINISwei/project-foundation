"""模組的 manifest: 一個模組對平台宣告它擁有什麼。

組裝層 (`app/registry.py`) 只決定啟用哪些 manifest, 不 import 模組的實作。
"""

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from fastapi import APIRouter

from shared.auth.identity import IdentityLoader
from shared.auth.permissions import PermissionSpec
from shared.db.base import Base
from shared.events import EventHandler
from shared.jobs import JobSpec, Schedule


@dataclass(frozen=True)
class ModuleManifest:
    name: str
    routers: tuple[APIRouter, ...] = ()
    #: 這個模組的資料表。列在這裡才會被載入, migration 才看得到。
    models: tuple[type[Base], ...] = ()
    permissions: tuple[PermissionSpec, ...] = ()
    #: 訂閱別的模組在 public.py 定義的事件。
    event_handlers: tuple[EventHandler, ...] = ()
    jobs: tuple[JobSpec, ...] = ()
    schedules: tuple[Schedule, ...] = ()
    #: 初始資料。每次 migrate 之後執行, 所以要能重複執行 (存在就更新, 不存在才新增)。
    seeders: tuple[Callable[[], Awaitable[None]], ...] = ()
    #: 依 id 取得登入者。整個 app 只能有一個模組提供 (擁有帳號資料的那個)。
    identity_loader: IdentityLoader | None = None


def validate_modules(modules: Iterable[ModuleManifest]) -> tuple[ModuleManifest, ...]:
    """擋下撞名: 模組、路由前綴、資料表、任務。這些撞名都不會自己報錯, 只會有一方安靜地失效。"""
    resolved = tuple(modules)
    seen: dict[str, set[str]] = {"模組": set(), "路由前綴": set(), "資料表": set(), "任務": set()}

    def claim(kind: str, value: str, module: ModuleManifest) -> None:
        if not value or value in seen[kind]:
            raise RuntimeError(f"{kind}重複或空白: {value!r} (模組 {module.name})")
        seen[kind].add(value)

    for module in resolved:
        claim("模組", module.name, module)
        for router in module.routers:
            claim("路由前綴", router.prefix, module)
        for model in module.models:
            claim("資料表", model.__tablename__, module)
        for job in module.jobs:
            claim("任務", job.name, module)
        unknown = [item.job.name for item in module.schedules if item.job not in module.jobs]
        if unknown:
            raise RuntimeError(f"排程用到沒有登記在 jobs 的任務: {unknown} (模組 {module.name})")
    if sum(module.identity_loader is not None for module in resolved) > 1:
        raise RuntimeError("只能有一個模組提供 identity_loader")
    return resolved
