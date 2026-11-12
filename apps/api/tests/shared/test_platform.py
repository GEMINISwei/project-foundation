"""每個請求共同經過的處理: 錯誤格式、追蹤 id、交易與 AUDIT。"""

import pytest

from tests.helpers import admin_headers, create_admin, create_role, login, scalar

pytestmark = pytest.mark.integration


async def test_health_endpoints_answer_without_login(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    assert (await client.get("/health/ready")).json() == {"status": "ok"}


async def test_errors_share_one_shape_and_carry_the_request_id(client):
    response = await client.get("/api/users/me")
    body = response.json()
    assert response.status_code == 401
    assert set(body) == {"code", "message", "request_id", "fields"}
    assert body["code"] == "auth.token_missing"
    assert response.headers["x-request-id"] == body["request_id"]


async def test_upstream_request_id_is_reused_only_when_it_is_safe_to_log(client):
    kept = await client.get("/api/users/me", headers={"X-Request-ID": "trace-0001"})
    assert kept.headers["x-request-id"] == "trace-0001"
    # 帶空白的值可以偽造出另一行 log, 不沿用。
    replaced = await client.get("/api/users/me", headers={"X-Request-ID": "bad id"})
    assert replaced.headers["x-request-id"] != "bad id"


async def test_message_follows_accept_language_but_code_does_not(client):
    zh = (await client.get("/api/users/me")).json()
    en = (await client.get("/api/users/me", headers={"Accept-Language": "en-US"})).json()
    assert zh["code"] == en["code"]
    assert zh["message"] != en["message"]


async def test_validation_errors_name_each_field(client):
    response = await client.post("/api/users/login", json={"username": ""})
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation.invalid"
    assert {item["field"] for item in body["fields"]} == {"username", "password"}


async def test_unknown_routes_use_the_same_error_shape(client):
    body = (await client.get("/api/does-not-exist")).json()
    assert body["code"] == "http.404"
    assert body["request_id"]


async def test_system_info_requires_login(client):
    assert (await client.get("/api/system/info")).status_code == 401
    info = (await client.get("/api/system/info", headers=await admin_headers(client))).json()
    assert info["languages"] == ["zh", "en"]


async def test_audit_is_kept_even_when_the_request_itself_is_rolled_back(client):
    await create_admin()
    response = await client.post(
        "/api/users/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401
    row = await scalar(
        "SELECT data->>'reason' FROM audit_logs WHERE event = 'login_failed' AND request_id = :id",
        id=response.headers["x-request-id"],
    )
    assert row == "bad_password"


async def test_audit_tells_whether_the_writes_of_the_request_were_committed(client):
    await create_admin()
    await client.post("/api/users/login", json={"username": "admin", "password": "wrong-password"})
    headers = await login(client, "admin")
    await create_role(client, headers, "Support", [])
    assert await scalar("SELECT committed FROM audit_logs WHERE event = 'login_failed'") is False
    assert await scalar("SELECT committed FROM audit_logs WHERE event = 'role_created'") is True


async def test_audit_records_who_did_it(client):
    admin_id = await create_admin()
    headers = await login(client, "admin")
    role = await create_role(client, headers, "Support", [])
    actor = await scalar(
        "SELECT actor_id FROM audit_logs WHERE event = 'role_created' AND data->>'role_id' = :id",
        id=role["id"],
    )
    assert actor == str(admin_id)


async def test_a_failed_request_leaves_no_partial_writes(client):
    headers = await admin_headers(client)
    await create_role(client, headers, "Support", [])
    # 第二次同名: 回 409, 資料庫裡仍然只有一筆。
    again = await client.post("/api/roles", headers=headers, json={"name": "Support"})
    assert again.status_code == 409
    assert await scalar("SELECT count(*) FROM roles WHERE name = 'Support'") == 1
