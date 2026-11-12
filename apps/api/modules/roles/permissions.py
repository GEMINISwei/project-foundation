from app.permissions import Permission
from shared.auth.permissions import PermissionSpec
from shared.i18n import LangText

_CATEGORY = LangText(zh="角色", en="Roles")

PERMISSIONS = (
    PermissionSpec(Permission.ROLES_READ, LangText(zh="查看", en="View"), _CATEGORY),
    PermissionSpec(
        Permission.ROLES_WRITE,
        LangText(zh="新增與修改", en="Create and edit"),
        _CATEGORY,
        requires=frozenset({Permission.ROLES_READ}),
    ),
)
