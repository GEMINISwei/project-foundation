"""這個專案所有的權限值。

集中定義是刻意的: enum 進 OpenAPI 後是字串聯集, 前端打錯權限名稱會編譯失敗。
命名一律 `資源:動作`。標籤、分類與相依關係由引入它的模組在自己的 `permissions.py` 宣告;
新增一個值而沒有模組宣告, 啟動時就會失敗。
"""

from shared.auth.permissions import WILDCARD, BasePermission


class Permission(BasePermission):
    """權限。`*` 是超級管理者, 只存在於系統角色。"""

    ALL = WILDCARD

    USERS_READ = "users:read"
    USERS_WRITE = "users:write"

    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
