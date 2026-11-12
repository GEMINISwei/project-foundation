"""users 資料表的查詢。回傳 ORM 物件, 不做業務判斷。"""

import uuid
from collections.abc import Iterable

from sqlalchemy import ColumnElement, or_, select, update

from shared.db.pagination import PageParams, PageResult, paginate
from shared.db.session import db

from .model import User, UserRole


async def get(user_id: uuid.UUID) -> User | None:
    return await db().get(User, user_id)


async def get_by_username(username: str) -> User | None:
    return await db().scalar(select(User).where(User.username == username))


async def page(
    params: PageParams,
    *,
    keyword: str | None,
    role_id: uuid.UUID | None,
    unassigned: bool,
    is_disabled: bool | None,
) -> PageResult[User]:
    conditions: list[ColumnElement[bool]] = []
    if keyword:
        conditions.append(
            or_(
                User.username.icontains(keyword, autoescape=True),
                User.nickname.icontains(keyword, autoescape=True),
            )
        )
    if role_id is not None:
        conditions.append(User.id.in_(select(UserRole.user_id).where(UserRole.role_id == role_id)))
    if unassigned:
        conditions.append(User.id.not_in(select(UserRole.user_id)))
    if is_disabled is not None:
        conditions.append(User.is_disabled == is_disabled)
    return await paginate(User, params, where=conditions)


async def add(user: User) -> User:
    db().add(user)
    await db().flush()
    return user


def set_roles(user: User, role_ids: Iterable[uuid.UUID]) -> None:
    wanted = set(role_ids)
    user.role_links = [link for link in user.role_links if link.role_id in wanted] + [
        UserRole(role_id=role_id) for role_id in wanted - set(user.role_ids)
    ]


async def set_password(
    user_id: uuid.UUID, password_hash: str, *, expected_auth_version: int | None = None
) -> int | None:
    """換密碼並讓既有的登入失效, 回傳新的 auth_version。

    給了 `expected_auth_version` 時只在版本沒變的情況下才寫入 (否則回傳 None): 舊密碼是對著
    當時讀到的雜湊比對的, 這段時間內別的請求換過密碼或登出了就不能覆寫。
    """
    statement = (
        update(User)
        .where(User.id == user_id)
        .values(password_hash=password_hash, auth_version=User.auth_version + 1)
        .returning(User.auth_version)
    )
    if expected_auth_version is not None:
        statement = statement.where(User.auth_version == expected_auth_version)
    return await db().scalar(statement)


async def revoke_sessions(user_id: uuid.UUID) -> None:
    await db().execute(
        update(User).where(User.id == user_id).values(auth_version=User.auth_version + 1)
    )


async def revoke_all_sessions() -> int:
    result = await db().execute(update(User).values(auth_version=User.auth_version + 1))
    return result.rowcount or 0  # type: ignore[attr-defined]
