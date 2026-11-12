from app.permissions import Permission
from shared.auth.permissions import PermissionSpec
from shared.i18n import LangText

_CATEGORY = LangText(zh="使用者", en="Users")

PERMISSIONS = (
    PermissionSpec(Permission.USERS_READ, LangText(zh="查看", en="View"), _CATEGORY),
    PermissionSpec(
        Permission.USERS_WRITE,
        LangText(zh="新增與修改", en="Create and edit"),
        _CATEGORY,
        # 指派角色時要列出角色清單, 所以連帶需要查看角色。
        requires=frozenset({Permission.USERS_READ, Permission.ROLES_READ}),
    ),
)
