from shared.errors import ErrorSpec
from shared.i18n import LangText

ROLE_NOT_FOUND = ErrorSpec(404, "roles.not_found", LangText(zh="角色不存在", en="Role not found"))
ROLE_NAME_EXISTS = ErrorSpec(
    409, "roles.name_exists", LangText(zh="角色名稱已存在", en="Role name already exists")
)
SYSTEM_ROLE_READONLY = ErrorSpec(
    403,
    "roles.system_role_readonly",
    LangText(zh="系統角色不可修改或停用", en="System roles cannot be modified or disabled"),
)
WILDCARD_NOT_ASSIGNABLE = ErrorSpec(
    403,
    "roles.wildcard_not_assignable",
    LangText(zh="一般角色不可使用最高權限", en="Regular roles cannot use the wildcard permission"),
)
CANNOT_MANAGE_HIGHER = ErrorSpec(
    403,
    "roles.cannot_manage_higher",
    LangText(
        zh="不能修改或停用權限比自己高的角色",
        en="You cannot modify or disable a role with more permissions than you have",
    ),
)
CANNOT_GRANT_UNOWNED = ErrorSpec(
    403,
    "roles.cannot_grant_unowned",
    LangText(zh="不能授予自己沒有的權限", en="You cannot grant permissions you do not have"),
)
