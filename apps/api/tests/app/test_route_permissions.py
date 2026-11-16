"""每條 API 路由的權限: 宣告了的真的擋得住, 沒宣告的必須明確標成公開。

逐條呼叫組好的 app, 新增的路由不必另外寫測試就會被涵蓋。每個情境用新建的帳號,
憑證直接簽發: 登入有限流, 而且登出、改密碼這類路由會讓同一個帳號的憑證失效。
"""

import re
import uuid
from typing import Annotated, NamedTuple

import httpx2
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute, iter_route_contexts

from app.server import app
from shared.auth.identity import Identity, public, require
from shared.auth.tokens import create_token
from shared.platform import API_PREFIX
from tests.helpers import admin_headers, create_role, create_user, scalar

pytestmark = pytest.mark.integration

Rule = str | tuple[str, ...] | None


def declared(route: APIRoute) -> Rule:
    found: Rule = None
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        if getattr(dependency.call, "public", False):
            return "public"
        required = getattr(dependency.call, "required_permissions", None)
        if required is not None:
            found = tuple(str(item) for item in required)
        pending.extend(dependency.dependencies)
    return found


class Route(NamedTuple):
    path: str
    methods: frozenset[str]
    route: APIRoute


def api_routes(application: FastAPI) -> list[Route]:
    result = []
    for context in iter_route_contexts(application.routes):
        route, path = context.original_route, context.path
        if isinstance(route, APIRoute) and path and path.startswith(API_PREFIX):
            result.append(Route(path, frozenset(context.methods or ()), route))
    return result


def calls(application: FastAPI) -> list[tuple[str, str, tuple[str, ...]]]:
    routes = api_routes(application)
    assert routes, "列不出任何 API 路由"
    result = []
    for item in routes:
        rule = declared(item.route)
        if isinstance(rule, tuple):
            path = re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), item.path)
            result += [(method, path, rule) for method in sorted(item.methods - {"HEAD"})]
    return result


async def token_for(
    client: httpx2.AsyncClient, admin: dict[str, str], permissions: tuple[str, ...]
) -> dict[str, str]:
    name = uuid.uuid4().hex[:10]
    roles = [(await create_role(client, admin, f"r{name}", list(permissions)))["id"]]
    user = await create_user(client, admin, f"u{name}", roles if permissions else [])
    version = await scalar("SELECT auth_version FROM users WHERE id = :id", id=user["id"])
    return {"Authorization": f"Bearer {create_token(uuid.UUID(user['id']), version)}"}


async def status(
    client: httpx2.AsyncClient, method: str, path: str, headers: dict[str, str]
) -> int:
    body: dict[str, object] | None = {} if method in ("POST", "PUT", "PATCH") else None
    response = await client.request(method, path, headers=headers, json=body)
    return response.status_code


def report(mismatches: list[str]) -> str:
    return "\n".join(["| 路由 | 情境 | 實際 |", "|---|---|---|", *mismatches])


def test_every_api_route_declares_its_permissions_or_is_marked_public() -> None:
    routes = api_routes(app)
    missing = [
        f"{','.join(sorted(item.methods))} {item.path}"
        for item in routes
        if declared(item.route) is None
    ]

    assert routes, "列不出任何 API 路由"
    assert missing == []


def test_a_route_without_require_or_public_is_reported() -> None:
    router = APIRouter()

    @router.get("/open")
    async def open_route() -> None: ...

    @router.get("/member")
    async def member_route(_: Annotated[Identity, Depends(require())]) -> None: ...

    @router.get("/login", dependencies=[Depends(public())])
    async def login_route() -> None: ...

    application = FastAPI()
    application.include_router(router, prefix=API_PREFIX)

    assert {item.path: declared(item.route) for item in api_routes(application)} == {
        "/api/open": None,
        "/api/member": (),
        "/api/login": "public",
    }


async def test_every_route_rejects_requests_without_a_login(client: httpx2.AsyncClient) -> None:
    mismatches = []
    for method, path, _ in calls(app):
        actual = await status(client, method, path, {})
        if actual != 401:
            mismatches.append(f"| {method} {path} | 沒有登入，應該 401 | {actual} |")

    assert mismatches == [], report(mismatches)


async def test_every_route_rejects_accounts_without_its_permissions(
    client: httpx2.AsyncClient,
) -> None:
    admin = await admin_headers(client)
    mismatches = []
    for method, path, permissions in calls(app):
        if not permissions:
            continue
        actual = await status(client, method, path, await token_for(client, admin, ()))
        if actual != 403:
            mismatches.append(
                f"| {method} {path} | 缺少 {', '.join(permissions)}，應該 403 | {actual} |"
            )

    assert mismatches == [], report(mismatches)


async def test_every_route_accepts_accounts_with_exactly_its_permissions(
    client: httpx2.AsyncClient,
) -> None:
    admin = await admin_headers(client)
    mismatches = []
    for method, path, permissions in calls(app):
        actual = await status(client, method, path, await token_for(client, admin, permissions))
        if actual in (401, 403):
            needed = ", ".join(permissions) or "只要登入"
            mismatches.append(f"| {method} {path} | 擁有 {needed}，不該被擋 | {actual} |")

    assert mismatches == [], report(mismatches)
