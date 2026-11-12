"""目前登入者與權限檢查。

路由用 `Depends(require(Permission.USERS_READ))` 宣告需要的權限; 不帶參數就是「只要登入」。

`shared` 不認識使用者資料表, 所以「怎麼依 id 取得使用者」由擁有帳號資料的模組在 manifest 的
`identity_loader` 提供, 平台啟動時放進 `app.state`。
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared import context
from shared.auth.permissions import BasePermission, has_permission
from shared.auth.tokens import TOKEN_REVOKED, parse_token
from shared.errors import ErrorSpec
from shared.i18n import LangText

FORBIDDEN = ErrorSpec(403, "auth.forbidden", LangText(zh="沒有權限執行這個操作", en="Forbidden"))


@dataclass(frozen=True)
class Identity:
    id: uuid.UUID
    username: str
    nickname: str
    auth_version: int
    is_disabled: bool
    #: 所有角色的權限聯集 (已補上相依的權限); 超級管理者是 `{"*"}`。
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return has_permission(self.permissions, permission)


IdentityLoader = Callable[[uuid.UUID], Awaitable[Identity | None]]

# auto_error=False: 沒帶憑證時由我們回 401 與自己的錯誤格式, 不是 FastAPI 預設的 403。
_bearer = HTTPBearer(auto_error=False)


def require(*permissions: BasePermission) -> Callable[..., Awaitable[Identity]]:
    async def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Identity:
        claims = parse_token(credentials.credentials if credentials else None)
        loader: IdentityLoader = request.app.state.identity_loader
        identity = await loader(claims.user_id)
        if identity is None or identity.is_disabled or identity.auth_version != claims.auth_version:
            raise TOKEN_REVOKED()
        context.set_user(str(identity.id))
        if not all(identity.can(permission) for permission in permissions):
            raise FORBIDDEN()
        return identity

    return dependency
