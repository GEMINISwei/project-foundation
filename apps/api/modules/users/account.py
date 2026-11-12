"""使用者對自己帳號的操作: 登入、登出、換密碼、改個人資料。

授權模型是「你就是這個帳號」, 不看權限。管理者對別人的操作在 `service.py`。
"""

from app.permissions import Permission
from shared.audit import audit
from shared.auth import passwords
from shared.auth.identity import Identity
from shared.auth.permissions import WILDCARD, PermissionCatalog
from shared.auth.tokens import create_token
from shared.db.session import db, release_connection
from shared.errors import found

from . import repository
from .errors import (
    CURRENT_PASSWORD_MISMATCH,
    INVALID_CREDENTIALS,
    PASSWORD_CHANGED_CONCURRENTLY,
    USER_NOT_FOUND,
)
from .schema import LoginRequest, Me, PasswordChange, ProfileUpdate, Token


async def login(data: LoginRequest) -> Token:
    user = await repository.get_by_username(data.username)
    # 雜湊比對約 0.2 秒, 這段時間不佔資料庫連線。
    await release_connection()
    matched = await passwords.verify_password(data.password, user.password_hash if user else None)
    if user is None or user.is_disabled or not matched:
        # 三種情況回同一個錯誤, 不讓回應洩漏帳號存不存在; 原因只留在 AUDIT。
        reason = (
            "unknown_account"
            if user is None
            else "disabled"
            if user.is_disabled
            else "bad_password"
        )
        audit("login_failed", reason=reason, user_id=user.id if user else None)
        raise INVALID_CREDENTIALS()
    audit("login_succeeded", user_id=user.id)
    return Token(access_token=create_token(user.id, user.auth_version))


def me(identity: Identity, catalog: PermissionCatalog) -> Me:
    # 超級管理者列出全部權限: 前端只比對字串, 不必另外認得萬用權限。
    names = [WILDCARD, *catalog.known()] if identity.can(WILDCARD) else sorted(identity.permissions)
    return Me(
        id=identity.id,
        username=identity.username,
        nickname=identity.nickname,
        permissions=[Permission(name) for name in names],
    )


async def logout(identity: Identity) -> None:
    """登出會讓這個帳號所有裝置的登入失效: 憑證是無狀態的, 只刪 cookie 的話被複製走的還能用。"""
    await repository.revoke_sessions(identity.id)
    audit("logout", user_id=identity.id)


async def update_profile(identity: Identity, data: ProfileUpdate) -> None:
    user = found(await repository.get(identity.id), USER_NOT_FOUND)
    user.nickname = data.nickname
    await db().flush()


async def change_password(identity: Identity, data: PasswordChange) -> Token:
    """換自己的密碼並拿回新的憑證: 換密碼會讓所有既有的登入失效, 包含發出這次請求的那一張。"""
    user = found(await repository.get(identity.id), USER_NOT_FOUND)
    current_hash, version = user.password_hash, user.auth_version
    await release_connection()
    if not await passwords.verify_password(data.current_password, current_hash):
        audit("password_change_failed", user_id=identity.id)
        raise CURRENT_PASSWORD_MISMATCH()
    new_hash = await passwords.hash_password(data.new_password)
    new_version = await repository.set_password(
        identity.id, new_hash, expected_auth_version=version
    )
    if new_version is None:
        raise PASSWORD_CHANGED_CONCURRENTLY()
    audit("password_changed", user_id=identity.id)
    return Token(access_token=create_token(identity.id, new_version))
