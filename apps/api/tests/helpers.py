"""integration 測試共用的建立資料與登入。"""

import uuid
from typing import Any

import httpx2
from sqlalchemy import text

from app.registry import ENABLED_MODULES
from modules.users.public import SuperAdminCreate, create_super_admin
from shared.db.session import engine
from shared.platform import event_bus, unit_of_work

PASSWORD = "Password#123"


async def create_admin(username: str = "admin") -> uuid.UUID:
    async with unit_of_work(event_bus(ENABLED_MODULES)):
        return await create_super_admin(
            SuperAdminCreate(username=username, nickname=username.title(), password=PASSWORD)
        )


async def login(
    client: httpx2.AsyncClient, username: str, password: str = PASSWORD
) -> dict[str, str]:
    response = await client.post(
        "/api/users/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def admin_headers(client: httpx2.AsyncClient) -> dict[str, str]:
    await create_admin()
    return await login(client, "admin")


async def create_role(
    client: httpx2.AsyncClient, headers: dict[str, str], name: str, permissions: list[str]
) -> dict[str, Any]:
    response = await client.post(
        "/api/roles", headers=headers, json={"name": name, "permissions": permissions}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def create_user(
    client: httpx2.AsyncClient,
    headers: dict[str, str],
    username: str,
    role_ids: list[str] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/users",
        headers=headers,
        json={
            "username": username,
            "nickname": username.title(),
            "password": PASSWORD,
            "role_ids": role_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def user_with(
    client: httpx2.AsyncClient, admin: dict[str, str], username: str, permissions: list[str]
) -> tuple[dict[str, Any], dict[str, str]]:
    """建立一個擁有指定權限的帳號, 回傳帳號資料與它的登入標頭。"""
    role = await create_role(client, admin, f"{username}-role", permissions)
    user = await create_user(client, admin, username, [role["id"]])
    return user, await login(client, username)


async def scalar(sql: str, **params: Any) -> Any:
    async with engine().connect() as connection:
        return (await connection.execute(text(sql), params)).scalar()
