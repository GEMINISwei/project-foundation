from shared.errors import ErrorSpec
from shared.i18n import LangText

USER_NOT_FOUND = ErrorSpec(404, "users.not_found", LangText(zh="使用者不存在", en="User not found"))
USERNAME_EXISTS = ErrorSpec(
    409, "users.username_exists", LangText(zh="帳號已存在", en="Username already exists")
)
INVALID_CREDENTIALS = ErrorSpec(
    401,
    "users.invalid_credentials",
    LangText(zh="帳號或密碼錯誤", en="Invalid username or password"),
)
# 403 而不是 401: 前端把 401 一律當成登入失效並導回登入頁, 「舊密碼打錯」不該變成「被登出」。
CURRENT_PASSWORD_MISMATCH = ErrorSpec(
    403,
    "users.current_password_mismatch",
    LangText(zh="目前密碼錯誤", en="Current password is incorrect"),
)
PASSWORD_CHANGED_CONCURRENTLY = ErrorSpec(
    409,
    "users.password_changed_concurrently",
    LangText(
        zh="密碼剛被其他操作變更，請重新登入後再試",
        en="Password was just changed elsewhere, please sign in again and retry",
    ),
)
CANNOT_CHANGE_SELF = ErrorSpec(
    403,
    "users.cannot_change_self",
    LangText(
        zh="不能停用自己或更改自己的角色", en="You cannot disable yourself or change your own roles"
    ),
)
SUPER_ADMIN_PROTECTED = ErrorSpec(
    403,
    "users.super_admin_protected",
    LangText(
        zh="超級管理者的帳號只能用指令管理",
        en="Super admin accounts can only be managed from the command line",
    ),
)
CANNOT_MANAGE_HIGHER = ErrorSpec(
    403,
    "users.cannot_manage_higher",
    LangText(
        zh="不能管理權限比自己高的帳號",
        en="You cannot manage accounts with more permissions than yours",
    ),
)
ROLE_NOT_ASSIGNABLE = ErrorSpec(
    400,
    "users.role_not_assignable",
    LangText(
        zh="指定的角色不存在、已停用或不可指派",
        en="A selected role is missing, disabled or not assignable",
    ),
)
CANNOT_ASSIGN_HIGHER_ROLE = ErrorSpec(
    403,
    "users.cannot_assign_higher_role",
    LangText(
        zh="不能指派含有自己沒有的權限的角色",
        en="You cannot assign roles with permissions you do not have",
    ),
)
