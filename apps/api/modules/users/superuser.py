"""只給指令用的帳號操作: 建立超級管理者、讓所有人登出。

授權模型是「呼叫者已經有主機的 shell」, 所以不接在任何路由上, 也不應該接:
這是唯一能產生超級管理者的路徑, 接上 HTTP 就得另外保管一組建立高權限帳號的秘密。
"""

import uuid

from pydantic import BaseModel

from modules.roles.public import get_super_admin_role_id
from shared.audit import audit
from shared.auth import passwords

from . import repository
from .errors import USERNAME_EXISTS
from .model import User
from .schema import NewPassword, Text


class SuperAdminCreate(BaseModel):
    username: Text
    nickname: Text
    password: NewPassword


async def create_super_admin(data: SuperAdminCreate) -> uuid.UUID:
    """可以重複執行: 第一個超管、第二個超管、唯一的超管失聯時的救援。"""
    if await repository.get_by_username(data.username):
        raise USERNAME_EXISTS()
    user = User(
        username=data.username,
        nickname=data.nickname,
        password_hash=await passwords.hash_password(data.password),
    )
    repository.set_roles(user, [await get_super_admin_role_id()])
    await repository.add(user)
    audit("superuser_created", user_id=user.id)
    return user.id


async def revoke_all_sessions() -> int:
    """讓所有人都要重新登入 (懷疑憑證外流時)。JWT_SECRET_KEY 本身外洩時這不夠, 要換金鑰。"""
    affected = await repository.revoke_all_sessions()
    audit("sessions_revoked_all", affected=affected)
    return affected
