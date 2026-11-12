import pytest

from app.permissions import Permission
from shared.auth.permissions import PermissionCatalog, PermissionSpec, has_permission
from shared.i18n import LangText

TEXT = LangText(zh="x", en="x")


def spec(value: Permission, *requires: Permission) -> PermissionSpec:
    return PermissionSpec(value, TEXT, TEXT, requires=frozenset(requires))


FULL = (
    spec(Permission.USERS_READ),
    spec(Permission.USERS_WRITE, Permission.USERS_READ, Permission.ROLES_READ),
    spec(Permission.ROLES_READ),
    spec(Permission.ROLES_WRITE, Permission.ROLES_READ),
)


def test_wildcard_grants_everything():
    assert has_permission({"*"}, "anything:at-all")
    assert has_permission({"users:read"}, "users:read")
    assert not has_permission({"users:read"}, "users:write")


def test_complete_adds_required_permissions_in_declaration_order():
    catalog = PermissionCatalog(Permission, FULL)
    assert catalog.complete(["users:write"]) == ["users:read", "users:write", "roles:read"]
    assert catalog.complete([]) == []


def test_complete_follows_requirements_transitively():
    chained = (
        spec(Permission.USERS_READ),
        spec(Permission.USERS_WRITE, Permission.ROLES_WRITE),
        spec(Permission.ROLES_READ, Permission.USERS_READ),
        spec(Permission.ROLES_WRITE, Permission.ROLES_READ),
    )
    assert set(PermissionCatalog(Permission, chained).complete(["users:write"])) == {
        "users:write",
        "roles:write",
        "roles:read",
        "users:read",
    }


@pytest.mark.parametrize(
    ("specs", "message"),
    [
        (FULL[:-1], "沒有模組宣告"),
        ((*FULL, spec(Permission.USERS_READ)), "重複宣告"),
    ],
)
def test_catalog_rejects_declarations_that_do_not_match_the_enum(specs, message):
    with pytest.raises(RuntimeError, match=message):
        PermissionCatalog(Permission, specs)
