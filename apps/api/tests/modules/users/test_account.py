"""使用者對自己帳號的操作: 登入、登出、換密碼、改個人資料。"""

import pytest

from modules.users import router
from shared.rate_limit import RateLimiter
from tests.helpers import PASSWORD, admin_headers, create_admin, create_user, login

pytestmark = pytest.mark.integration


async def test_wrong_password_unknown_account_and_disabled_account_look_the_same(client):
    admin = await admin_headers(client)
    user = await create_user(client, admin, "leaver")
    await client.post(f"/api/users/{user['id']}/disable", headers=admin)

    attempts = [
        {"username": "admin", "password": "wrong-password"},
        {"username": "ghost", "password": PASSWORD},
        {"username": "leaver", "password": PASSWORD},
    ]
    bodies = [(await client.post("/api/users/login", json=body)).json() for body in attempts]
    assert {body["code"] for body in bodies} == {"users.invalid_credentials"}
    assert len({body["message"] for body in bodies}) == 1


async def test_me_lists_every_permission_for_the_super_admin(client):
    me = (await client.get("/api/users/me", headers=await admin_headers(client))).json()
    assert me["username"] == "admin"
    assert me["permissions"] == ["*", "users:read", "users:write", "roles:read", "roles:write"]


async def test_logout_revokes_every_token_of_that_account_only(client):
    await create_admin("first")
    await create_admin("second")
    one, another, other = (
        await login(client, "first"),
        await login(client, "first"),
        await login(client, "second"),
    )
    assert (await client.post("/api/users/me/logout", headers=one)).status_code == 204
    assert (await client.get("/api/users/me", headers=another)).json()[
        "code"
    ] == "auth.token_revoked"
    assert (await client.get("/api/users/me", headers=other)).status_code == 200


async def test_changing_password_returns_a_working_token_and_revokes_the_old_one(client):
    old = await admin_headers(client)
    response = await client.put(
        "/api/users/me/password",
        headers=old,
        json={"current_password": PASSWORD, "new_password": "Brand-New#456"},
    )
    assert response.status_code == 200
    fresh = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert (await client.get("/api/users/me", headers=fresh)).status_code == 200
    assert (await client.get("/api/users/me", headers=old)).status_code == 401
    await login(client, "admin", "Brand-New#456")


async def test_a_wrong_current_password_is_403_so_the_browser_is_not_logged_out(client):
    headers = await admin_headers(client)
    response = await client.put(
        "/api/users/me/password",
        headers=headers,
        json={"current_password": "not-it", "new_password": "Brand-New#456"},
    )
    assert (response.status_code, response.json()["code"]) == (
        403,
        "users.current_password_mismatch",
    )
    assert (await client.get("/api/users/me", headers=headers)).status_code == 200


@pytest.mark.parametrize("password", ["short", "x" * 73])
async def test_new_passwords_must_fit_the_policy(client, password):
    response = await client.put(
        "/api/users/me/password",
        headers=await admin_headers(client),
        json={"current_password": PASSWORD, "new_password": password},
    )
    assert response.status_code == 422
    assert response.json()["fields"][0]["field"] == "new_password"


async def test_profile_update_changes_only_the_nickname(client):
    headers = await admin_headers(client)
    response = await client.patch("/api/users/me", headers=headers, json={"nickname": "  New  "})
    assert response.status_code == 204
    assert (await client.get("/api/users/me", headers=headers)).json()["nickname"] == "New"


async def test_repeated_failed_logins_are_rate_limited(client, monkeypatch):
    await create_admin()
    monkeypatch.setattr(
        router, "login_limiter", RateLimiter("login", max_attempts=2, window_seconds=60)
    )
    wrong = {"username": "admin", "password": "wrong-password"}
    statuses = [(await client.post("/api/users/login", json=wrong)).status_code for _ in range(3)]
    assert statuses == [401, 401, 429]
    # 被擋下之後, 連正確的密碼也進不去, 直到窗口過去。
    blocked = await client.post(
        "/api/users/login", json={"username": "admin", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers


async def test_a_successful_login_clears_the_per_account_counter(client, monkeypatch):
    await create_admin()
    monkeypatch.setattr(
        router, "login_limiter", RateLimiter("login", max_attempts=2, window_seconds=60)
    )
    await client.post("/api/users/login", json={"username": "admin", "password": "wrong-password"})
    await login(client, "admin")
    await client.post("/api/users/login", json={"username": "admin", "password": "wrong-password"})
    await login(client, "admin")
