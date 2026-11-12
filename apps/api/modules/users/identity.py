"""登入者的身分: 平台的權限檢查經由 manifest 的 `identity_loader` 呼叫這裡。

每個請求固定三次查詢 (使用者、他的角色關聯、角色內容), 不隨資料量增加。
"""

import uuid

from modules.roles.public import RoleSummary, effective_permissions, get_roles
from shared.auth.identity import Identity

from . import repository
from .model import User


def to_identity(user: User, roles: list[RoleSummary]) -> Identity:
    return Identity(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        auth_version=user.auth_version,
        is_disabled=user.is_disabled,
        permissions=effective_permissions(roles),
    )


async def load_identity(user_id: uuid.UUID) -> Identity | None:
    user = await repository.get(user_id)
    if user is None:
        return None
    return to_identity(user, await get_roles(user.role_ids))
