"""管理者對其他使用者的操作, 重點在「有權限也不該做」的那幾條。"""

import pytest

from tests.helpers import (
    PASSWORD,
    admin_headers,
    create_admin,
    create_role,
    create_user,
    login,
    scalar,
    user_with,
)

pytestmark = pytest.mark.integration


def update_body(user, **changes):
    body = {
        "nickname": user["nickname"],
        "is_disabled": user["is_disabled"],
        "role_ids": [role["id"] for role in user["roles"]],
    }
    return {**body, **changes}


async def test_created_users_come_back_with_their_roles(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Support", ["users:read"])
    user = await create_user(client, admin, "amy", [role["id"]])
    assert user["roles"] == [
        {"id": role["id"], "name": "Support", "code": None, "is_disabled": False}
    ]
    assert "password" not in str(user)


async def test_usernames_are_unique(client):
    admin = await admin_headers(client)
    await create_user(client, admin, "amy")
    response = await client.post(
        "/api/users",
        headers=admin,
        json={"username": "amy", "nickname": "Amy 2", "password": PASSWORD},
    )
    assert (response.status_code, response.json()["code"]) == (409, "users.username_exists")


async def test_the_super_admin_role_cannot_be_assigned_from_the_web(client):
    admin = await admin_headers(client)
    super_role = str(await scalar("SELECT id FROM roles WHERE code = 'super_admin'"))
    response = await client.post(
        "/api/users",
        headers=admin,
        json={"username": "x", "nickname": "X", "password": PASSWORD, "role_ids": [super_role]},
    )
    assert response.json()["code"] == "users.role_not_assignable"


async def test_missing_or_disabled_roles_cannot_be_assigned(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Old", [])
    await client.post(f"/api/roles/{role['id']}/disable", headers=admin)
    for role_id in (role["id"], "01a1c874-0000-7000-8000-000000000000"):
        response = await client.post(
            "/api/users",
            headers=admin,
            json={"username": "x", "nickname": "X", "password": PASSWORD, "role_ids": [role_id]},
        )
        assert response.json()["code"] == "users.role_not_assignable"


async def test_super_admin_accounts_are_untouchable_from_the_web(client):
    admin_id = await create_admin()
    await create_admin("other")
    other = await login(client, "other")
    user = (await client.get(f"/api/users/{admin_id}", headers=other)).json()

    responses = [
        await client.put(f"/api/users/{admin_id}", headers=other, json=update_body(user)),
        await client.post(f"/api/users/{admin_id}/disable", headers=other),
        await client.put(
            f"/api/users/{admin_id}/password", headers=other, json={"password": PASSWORD}
        ),
    ]
    assert {response.json()["code"] for response in responses} == {"users.super_admin_protected"}


async def test_nobody_can_disable_themselves_or_change_their_own_roles(client):
    admin = await admin_headers(client)
    me, headers = await user_with(client, admin, "manager", ["users:write"])

    disable = await client.post(f"/api/users/{me['id']}/disable", headers=headers)
    drop_roles = await client.put(
        f"/api/users/{me['id']}", headers=headers, json=update_body(me, role_ids=[])
    )
    rename = await client.put(
        f"/api/users/{me['id']}", headers=headers, json=update_body(me, nickname="Renamed")
    )
    assert disable.json()["code"] == drop_roles.json()["code"] == "users.cannot_change_self"
    assert rename.status_code == 200


async def test_a_manager_cannot_take_over_an_account_with_more_permissions(client):
    admin = await admin_headers(client)
    _, manager = await user_with(client, admin, "manager", ["users:write"])
    stronger, _ = await user_with(client, admin, "stronger", ["users:write", "roles:write"])

    responses = [
        await client.put(
            f"/api/users/{stronger['id']}/password", headers=manager, json={"password": PASSWORD}
        ),
        await client.post(f"/api/users/{stronger['id']}/disable", headers=manager),
        await client.put(
            f"/api/users/{stronger['id']}", headers=manager, json=update_body(stronger)
        ),
    ]
    assert {response.json()["code"] for response in responses} == {"users.cannot_manage_higher"}


async def test_a_manager_cannot_hand_out_roles_beyond_their_own_permissions(client):
    admin = await admin_headers(client)
    _, manager = await user_with(client, admin, "manager", ["users:write"])
    bigger = await create_role(client, admin, "Role Admin", ["roles:write"])
    equal = await create_role(client, admin, "Readers", ["users:read"])

    denied = await client.post(
        "/api/users",
        headers=manager,
        json={"username": "x", "nickname": "X", "password": PASSWORD, "role_ids": [bigger["id"]]},
    )
    allowed = await client.post(
        "/api/users",
        headers=manager,
        json={"username": "y", "nickname": "Y", "password": PASSWORD, "role_ids": [equal["id"]]},
    )
    assert denied.json()["code"] == "users.cannot_assign_higher_role"
    assert allowed.status_code == 201


async def test_disabling_or_resetting_a_password_ends_that_users_sessions(client):
    admin = await admin_headers(client)
    first = await create_user(client, admin, "first")
    second = await create_user(client, admin, "second")
    first_session, second_session = await login(client, "first"), await login(client, "second")

    await client.post(f"/api/users/{first['id']}/disable", headers=admin)
    reset = await client.put(
        f"/api/users/{second['id']}/password", headers=admin, json={"password": "Reset#12345"}
    )
    assert reset.status_code == 204
    assert (await client.get("/api/users/me", headers=first_session)).status_code == 401
    assert (await client.get("/api/users/me", headers=second_session)).status_code == 401
    await login(client, "second", "Reset#12345")


async def test_changing_roles_takes_effect_on_the_next_request(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Readers", ["users:read"])
    user = await create_user(client, admin, "amy")
    session = await login(client, "amy")
    assert (await client.get("/api/users", headers=session)).status_code == 403

    await client.put(
        f"/api/users/{user['id']}", headers=admin, json=update_body(user, role_ids=[role["id"]])
    )
    assert (await client.get("/api/users", headers=session)).status_code == 200


async def test_list_filters(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Support", [])
    await create_user(client, admin, "amy", [role["id"]])
    bob = await create_user(client, admin, "bob")
    await client.post(f"/api/users/{bob['id']}/disable", headers=admin)

    async def names(**params):
        body = (await client.get("/api/users", headers=admin, params=params)).json()
        return sorted(user["username"] for user in body["items"])

    assert await names(keyword="AM") == ["amy"]
    assert await names(role_id=role["id"]) == ["amy"]
    assert await names(unassigned=True) == ["bob"]
    assert await names(is_disabled=True) == ["bob"]
    assert await names() == ["admin", "amy", "bob"]


async def test_listing_users_does_not_query_once_per_row(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Support", [])
    for index in range(6):
        await create_user(client, admin, f"user{index}", [role["id"]])

    from sqlalchemy import event

    from shared.db.session import engine

    statements: list[str] = []

    def count(_conn, _cursor, statement, *_):
        statements.append(statement)

    event.listen(engine().sync_engine, "before_cursor_execute", count)
    try:
        few = len(statements)
        await client.get("/api/users", headers=admin, params={"limit": 2})
        for_two = len(statements) - few
        await client.get("/api/users", headers=admin, params={"limit": 6})
        for_six = len(statements) - few - for_two
    finally:
        event.remove(engine().sync_engine, "before_cursor_execute", count)
    assert for_two == for_six
