"""把 shared 的各項能力接成可以運作的 app, 以及 HTTP 以外入口共用的進入點。

每個請求固定經過: 語系 → 追蹤 id → 資料庫交易 → 路由 → commit 或 rollback → AUDIT → 請求紀錄。
平台多一項「每個入口都要有」的東西時, 只改這個檔案的 `unit_of_work()`。
"""

import time
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: TID251
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared import audit, context
from shared.auth.identity import Identity, require
from shared.auth.permissions import BasePermission, PermissionCatalog
from shared.db.integrity import foreign_key_error
from shared.db.session import engine, session_scope, start_engine, stop_engine
from shared.errors import (
    FIELD_INVALID,
    FIELD_MESSAGES,
    INTERNAL,
    VALIDATION,
    AppError,
    ErrorBody,
    ErrorSpec,
    FieldError,
)
from shared.events import EventBus, use_event_bus
from shared.i18n import LangText, Language, current_language, resolve_language
from shared.jobs import JobSpec, Schedule
from shared.jobs.builtin import BUILTIN_JOBS, BUILTIN_SCHEDULES
from shared.logging import configure_logging, get_logger, init_error_tracking
from shared.module import ModuleManifest, validate_modules
from shared.settings import settings

#: 模組的路由都掛在這個前綴底下; 前端的 API 層會補上同一段。
API_PREFIX = "/api"
#: 探活路徑不開交易也不留紀錄。只放探活: 長出第二種用途就變成「某些請求不留紀錄」的後門。
HEALTH_PREFIX = "/health"
REQUEST_ID_HEADER = "X-Request-ID"
#: 超過這個耗時的請求記成 warning, `make logs errors` 就挑得出來。
SLOW_REQUEST_MS = 1000

log = get_logger(__name__)


@asynccontextmanager
async def unit_of_work(bus: EventBus) -> AsyncIterator[AsyncSession]:
    """一個工作單元: 事件訂閱表、資料庫交易、AUDIT。HTTP 請求、任務與 CLI 都經過這裡。"""
    audit.begin_collecting()
    committed = False
    try:
        with use_event_bus(bus):
            async with session_scope() as session:
                yield session
        committed = True
    finally:
        await audit.flush(committed=committed)


def event_bus(modules: Iterable[ModuleManifest]) -> EventBus:
    return EventBus(handler for module in modules for handler in module.event_handlers)


def all_jobs(modules: Iterable[ModuleManifest]) -> tuple[JobSpec, ...]:
    return (*BUILTIN_JOBS, *(job for module in modules for job in module.jobs))


def all_schedules(modules: Iterable[ModuleManifest]) -> tuple[Schedule, ...]:
    return (*BUILTIN_SCHEDULES, *(item for module in modules for item in module.schedules))


@asynccontextmanager
async def platform_scope(modules: Iterable[ModuleManifest]) -> AsyncIterator[AsyncSession]:
    """CLI 的進入點: 啟動引擎, 開一個與 HTTP 請求相同的工作單元, 結束時關閉引擎。"""
    start_engine()
    try:
        async with unit_of_work(event_bus(modules)) as session:
            yield session
    finally:
        await stop_engine()


# ── 錯誤回應 ─────────────────────────────────────────────────────────────────


def error_response(
    spec: ErrorSpec,
    *,
    fields: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorBody(
        code=spec.code,
        message=spec.text.resolve(),
        request_id=context.request_id.get(),
        fields=fields or [],
    )
    return JSONResponse(body.model_dump(), status_code=spec.status, headers=headers)


async def _app_error_handler(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, AppError)  # noqa: S101
    return error_response(error.spec, fields=error.fields, headers=error.headers)


async def _validation_handler(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)  # noqa: S101
    fields = [
        FieldError(
            # 只留欄位名: 前端的表單不認得 body/query 這層前綴。
            field=".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
            message=FIELD_MESSAGES.get(item["type"], FIELD_INVALID).resolve(),
        )
        for item in error.errors()
    ]
    return error_response(VALIDATION, fields=fields)


async def _integrity_handler(_request: Request, error: Exception) -> JSONResponse:
    """外鍵違反統一轉成 409, 模組只要在資料庫宣告 RESTRICT。唯一約束等其他情況由模組自己判斷。"""
    assert isinstance(error, IntegrityError)  # noqa: S101
    spec = foreign_key_error(error)
    if spec is None:
        raise error
    return error_response(spec)


async def _http_error_handler(_request: Request, error: Exception) -> JSONResponse:
    """框架自己丟的錯誤 (沒有這條路由、方法不允許) 也用同一種回應格式。"""
    assert isinstance(error, StarletteHTTPException)  # noqa: S101
    text_ = LangText(zh="請求無法處理", en=str(error.detail))
    return error_response(ErrorSpec(error.status_code, f"http.{error.status_code}", text_))


# ── 每個請求的共同處理 ───────────────────────────────────────────────────────


class PlatformMiddleware:
    """純 ASGI middleware: 與路由在同一個 task 裡執行, 路由設定的情境 (登入者) 這裡讀得到。

    回應先收在記憶體, 交易 commit 之後才送出: 用戶端收到成功時資料一定已經寫入, 緊接著的下一個
    請求讀得到; commit 失敗也還來得及改回 500。代價是不支援串流回應。
    """

    def __init__(self, app: ASGIApp, bus: EventBus) -> None:
        self.app = app
        self.bus = bus

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(HEALTH_PREFIX):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        current_language.set(resolve_language(headers.get("accept-language")))
        client = scope.get("client")
        request_id = context.begin(
            trace_id=headers.get(REQUEST_ID_HEADER),
            # web 轉來的用戶端 IP; 直接連 api 時 (測試、內網) 才用連線的來源。
            ip=headers.get("x-real-ip") or (client[0] if client else None),
        )
        started = time.perf_counter()
        messages = await self._run(scope, receive)
        status: int = messages[0]["status"]
        MutableHeaders(scope=messages[0])[REQUEST_ID_HEADER] = request_id
        for message in messages:
            await send(message)

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        level = "error" if status >= 500 else "warning" if duration_ms > SLOW_REQUEST_MS else "info"
        # 不記 query string: 敏感內容會長期留在 log 裡。
        getattr(log, level)(
            "request",
            method=scope["method"],
            path=scope["path"],
            status=status,
            duration_ms=duration_ms,
            ip=context.client_ip.get(),
        )

    async def _run(self, scope: Scope, receive: Receive) -> list[Message]:
        messages: list[Message] = []

        async def collect(message: Message) -> None:
            messages.append(message)

        try:
            async with unit_of_work(self.bus) as session:
                await self.app(scope, receive, collect)
                # 先寫入再回 4xx 的路徑不能把寫入 commit 進去。
                if messages and messages[0]["status"] >= 400:
                    await session.rollback()
                    audit.mark_rolled_back()
            return messages
        except Exception:
            log.exception("unhandled_error", method=scope["method"], path=scope["path"])
            return await _render(error_response(INTERNAL), scope)


async def _render(response: JSONResponse, scope: Scope) -> list[Message]:
    messages: list[Message] = []

    async def collect(message: Message) -> None:
        messages.append(message)

    async def no_body() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    await response(scope, no_body, collect)
    return messages


# ── 平台自己的路由 ───────────────────────────────────────────────────────────


class SystemInfo(BaseModel):
    """系統資訊。"""

    name: str
    version: str
    languages: list[Language]


def _platform_routers(app_version: str) -> tuple[APIRouter, APIRouter]:
    health = APIRouter(prefix=HEALTH_PREFIX, include_in_schema=False)

    @health.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @health.get("/ready")
    async def ready() -> dict[str, str]:
        # 真的查一次資料庫: 沒有資料庫就服務不了任何一條路由。
        async with engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    system = APIRouter(prefix="/system", tags=["system"])

    @system.get("/info")
    async def get_system_info(_: Identity = Depends(require())) -> SystemInfo:
        """系統名稱、目前執行的版本與支援的語系。"""
        # 要求登入: 未登入就查得到確切版本, 等於替人對照已知漏洞。
        return SystemInfo(name=settings.project_name, version=app_version, languages=list(Language))

    return health, system


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    start_engine()
    log.info(
        "api_started",
        version=app.state.app_version,
        mode=settings.mode,
        modules=[module.name for module in app.state.modules],
    )
    # 開機時刻意不寫任何資料: migration 與初始資料屬於 migrate 服務, 失敗時服務還沒切換。
    yield
    await stop_engine()


def create_platform_app(
    *,
    modules: Iterable[ModuleManifest],
    permissions: type[BasePermission],
    app_version: str,
) -> FastAPI:
    resolved = validate_modules(modules)
    configure_logging(json_output=settings.is_production)
    init_error_tracking(app_version)

    responses: dict[int | str, dict[str, Any]] = {"default": {"model": ErrorBody}}
    # OpenAPI 的 info.version 固定不動: 前後端同一個 repo、一起部署,
    # 契約的變更看 contracts/openapi.json 的 diff。
    app = FastAPI(
        # 固定的標題: 契約檔不該隨專案名稱或執行環境改變。
        title="API",
        version="1",
        lifespan=_lifespan,
        responses=responses,
        # 不提供線上的互動式文件: 瀏覽器碰不到 api, 契約看 contracts/openapi.json。
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.app_version = app_version
    app.state.modules = resolved
    app.state.permission_catalog = PermissionCatalog(
        permissions, (spec for module in resolved for spec in module.permissions)
    )
    app.state.identity_loader = next(
        (module.identity_loader for module in resolved if module.identity_loader), None
    )

    app.add_middleware(PlatformMiddleware, bus=event_bus(resolved))
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(IntegrityError, _integrity_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)

    health, system = _platform_routers(app_version)
    app.include_router(health)
    app.include_router(system, prefix=API_PREFIX)
    for module in resolved:
        for router in module.routers:
            app.include_router(router, prefix=API_PREFIX)
    return app
