"""這裡的 docstring 會進 OpenAPI 與前端型別檔, 只寫給呼叫端看的說明。"""

import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.permissions import Permission
from shared.auth.passwords import MAX_PASSWORD_BYTES

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def _within_bcrypt_limit(value: str) -> str:
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must not exceed {MAX_PASSWORD_BYTES} bytes")
    return value


# 比對既有密碼只要求非空: 它可能是在規則變嚴之前設的, 拿新規則擋它會讓最該換密碼的人換不了。
Password = Annotated[str, StringConstraints(min_length=1), AfterValidator(_within_bcrypt_limit)]
NewPassword = Annotated[str, StringConstraints(min_length=8), AfterValidator(_within_bcrypt_limit)]


class LoginRequest(BaseModel):
    username: Text
    password: Password


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — 憑證的種類, 不是密碼


class UserCreate(BaseModel):
    username: Text
    nickname: Text
    password: NewPassword
    role_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    nickname: Text
    is_disabled: bool
    role_ids: list[uuid.UUID]


class PasswordReset(BaseModel):
    password: NewPassword


class ProfileUpdate(BaseModel):
    nickname: Text


class PasswordChange(BaseModel):
    current_password: Password
    new_password: NewPassword


class RoleRef(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    is_disabled: bool


class UserInfo(BaseModel):
    id: uuid.UUID
    username: str
    nickname: str
    is_disabled: bool
    roles: list[RoleRef]


class Me(BaseModel):
    """目前登入者。`permissions` 是所有角色合起來的完整集合。"""

    id: uuid.UUID
    username: str
    nickname: str
    permissions: list[Permission]
