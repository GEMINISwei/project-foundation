import pytest

from tests.helpers import admin_headers, create_role, scalar, user_with

pytestmark = pytest.mark.integration


async def test_saving_a_role_adds_the_permissions_it_depends_on(client):
    headers = await admin_headers(client)
    role = await create_role(client, headers, "User Manager", ["users:write"])
    assert role["permissions"] == ["users:read", "users:write", "roles:read"]
    assert role["code"] is None


async def test_role_names_are_unique(client):
    headers = await admin_headers(client)
    await create_role(client, headers, "Support", [])
    response = await client.post("/api/roles", headers=headers, json={"name": "Support"})
    assert (response.status_code, response.json()["code"]) == (409, "roles.name_exists")


async def test_the_wildcard_can_never_be_given_to_a_regular_role(client):
    headers = await admin_headers(client)
    response = await client.post(
        "/api/roles", headers=headers, json={"name": "Sneaky", "permissions": ["*"]}
    )
    assert response.json()["code"] == "roles.wildcard_not_assignable"


async def test_system_roles_cannot_be_changed_or_disabled(client):
    headers = await admin_headers(client)
    role_id = await scalar("SELECT id FROM roles WHERE code = 'super_admin'")
    update = await client.put(
        f"/api/roles/{role_id}",
        headers=headers,
        json={"name": "Renamed", "permissions": [], "is_disabled": False},
    )
    disable = await client.post(f"/api/roles/{role_id}/disable", headers=headers)
    assert update.json()["code"] == disable.json()["code"] == "roles.system_role_readonly"


async def test_reading_and_writing_need_their_own_permissions(client):
    admin = await admin_headers(client)
    _, reader = await user_with(client, admin, "reader", ["roles:read"])
    _, nobody = await user_with(client, admin, "nobody", [])

    assert (await client.get("/api/roles", headers=reader)).status_code == 200
    assert (await client.get("/api/roles", headers=nobody)).status_code == 403
    denied = await client.post("/api/roles", headers=reader, json={"name": "X"})
    assert denied.json()["code"] == "auth.forbidden"


async def test_nobody_can_grant_a_permission_they_do_not_hold(client):
    admin = await admin_headers(client)
    _, editor = await user_with(client, admin, "editor", ["roles:write"])

    allowed = await client.post(
        "/api/roles", headers=editor, json={"name": "Mine", "permissions": ["roles:read"]}
    )
    escalated = await client.post(
        "/api/roles", headers=editor, json={"name": "More", "permissions": ["users:write"]}
    )
    assert allowed.status_code == 201
    assert escalated.json()["code"] == "roles.cannot_grant_unowned"


async def test_roles_above_your_own_permissions_cannot_be_changed_or_disabled(client):
    admin = await admin_headers(client)
    target = await create_role(client, admin, "Target", ["users:read"])
    _, editor = await user_with(client, admin, "editor", ["roles:write"])
    unchanged = {"name": "Target", "permissions": ["users:read"], "is_disabled": False}

    renamed = await client.put(
        f"/api/roles/{target['id']}", headers=editor, json={**unchanged, "name": "Renamed"}
    )
    narrowed = await client.put(
        f"/api/roles/{target['id']}", headers=editor, json={**unchanged, "permissions": []}
    )
    disabled = await client.post(f"/api/roles/{target['id']}/disable", headers=editor)

    codes = {response.json()["code"] for response in (renamed, narrowed, disabled)}
    assert codes == {"roles.cannot_manage_higher"}
    assert await scalar("SELECT is_disabled FROM roles WHERE name = 'Target'") is False


async def test_a_disabled_role_above_your_own_permissions_cannot_be_re_enabled(client):
    admin = await admin_headers(client)
    target = await create_role(client, admin, "Target", ["users:read"])
    await client.post(f"/api/roles/{target['id']}/disable", headers=admin)
    _, editor = await user_with(client, admin, "editor", ["roles:write"])

    response = await client.put(
        f"/api/roles/{target['id']}",
        headers=editor,
        json={"name": "Target", "permissions": ["users:read"], "is_disabled": False},
    )
    assert response.json()["code"] == "roles.cannot_manage_higher"
    assert await scalar("SELECT is_disabled FROM roles WHERE name = 'Target'") is True


async def test_roles_within_your_own_permissions_can_be_managed(client):
    admin = await admin_headers(client)
    target = await create_role(client, admin, "Target", ["roles:read"])
    _, editor = await user_with(client, admin, "editor", ["roles:write"])

    disabled = await client.post(f"/api/roles/{target['id']}/disable", headers=editor)
    enabled = await client.put(
        f"/api/roles/{target['id']}",
        headers=editor,
        json={"name": "Renamed", "permissions": ["roles:read"], "is_disabled": False},
    )
    widened = await client.put(
        f"/api/roles/{target['id']}",
        headers=editor,
        json={"name": "Renamed", "permissions": ["users:write"], "is_disabled": False},
    )
    assert (disabled.status_code, enabled.status_code) == (200, 200)
    assert widened.json()["code"] == "roles.cannot_grant_unowned"


async def test_a_disabled_role_stops_granting_its_permissions(client):
    admin = await admin_headers(client)
    role = await create_role(client, admin, "Readers", ["users:read"])
    from tests.helpers import create_user, login

    await create_user(client, admin, "reader", [role["id"]])
    reader = await login(client, "reader")
    assert (await client.get("/api/users", headers=reader)).status_code == 200

    await client.post(f"/api/roles/{role['id']}/disable", headers=admin)
    assert (await client.get("/api/users", headers=reader)).status_code == 403


async def test_list_filters_and_options(client):
    headers = await admin_headers(client)
    await create_role(client, headers, "Support Lead", [])
    off = await create_role(client, headers, "Old Team", [])
    await client.post(f"/api/roles/{off['id']}/disable", headers=headers)

    by_name = (await client.get("/api/roles", headers=headers, params={"name": "support"})).json()
    disabled = (
        await client.get("/api/roles", headers=headers, params={"is_disabled": True})
    ).json()
    options = (await client.get("/api/roles/options", headers=headers)).json()
    assert [role["name"] for role in by_name["items"]] == ["Support Lead"]
    assert [role["name"] for role in disabled["items"]] == ["Old Team"]
    assert len(options["items"]) == 3  # 加上系統角色


async def test_permission_options_are_grouped_and_translated(client):
    headers = await admin_headers(client)
    zh = (await client.get("/api/roles/permission-options", headers=headers)).json()["items"]
    en = (
        await client.get(
            "/api/roles/permission-options", headers={**headers, "Accept-Language": "en"}
        )
    ).json()["items"]
    assert [item["value"] for item in zh] == [
        "users:read",
        "users:write",
        "roles:read",
        "roles:write",
    ]
    assert zh[1]["requires"] == ["roles:read", "users:read"]
    assert (zh[0]["category"], en[0]["category"]) == ("使用者", "Users")


async def test_cursor_pagination_walks_forward_and_back_without_gaps(client):
    headers = await admin_headers(client)
    for index in range(5):
        await create_role(client, headers, f"Role {index}", [])

    async def page(**params):
        return (
            await client.get("/api/roles", headers=headers, params={"limit": 2, **params})
        ).json()

    first = await page()
    second = await page(cursor=first["next_cursor"])
    third = await page(cursor=second["next_cursor"])
    back = await page(cursor=third["prev_cursor"], direction="prev")

    names = [role["name"] for body in (first, second, third) for role in body["items"]]
    assert len(names) == len(set(names)) == 6  # 5 個加上系統角色
    assert first["total"] == 6
    assert (first["prev_cursor"], third["next_cursor"]) == (None, None)
    assert back["items"] == second["items"]


async def test_a_broken_cursor_is_a_client_error(client):
    headers = await admin_headers(client)
    response = await client.get("/api/roles", headers=headers, params={"cursor": "garbage"})
    assert (response.status_code, response.json()["code"]) == (400, "pagination.invalid_cursor")
