"""管理者對其他使用者的操作: 建立、查詢、修改、重設密碼、停用。

路由已經檢查過 `users:read`／`users:write`。這裡守的是有權限也不該做的事, 全部為了同一件事:
後台的操作不能用來提權或把別人鎖在外面。

- 不能停用自己、不能改自己的角色。
- 超級管理者的帳號後台完全不能動 (只能用指令), 超級管理者角色也不能指派。
- 非超級管理者只能管理權限不超過自己的帳號, 只能指派權限不超過自己的角色。
"""

import uuid

from sqlalchemy.exc import IntegrityError

from modules.roles.public import RoleSummary, get_roles
from shared.audit import audit
from shared.auth import passwords
from shared.auth.identity import Identity
from shared.auth.permissions import WILDCARD
from shared.db.integrity import is_unique_violation
from shared.db.pagination import Page, PageParams
from shared.db.session import db, release_connection
from shared.errors import found

from . import repository
from .errors import (
    CANNOT_ASSIGN_HIGHER_ROLE,
    CANNOT_CHANGE_SELF,
    CANNOT_MANAGE_HIGHER,
    ROLE_NOT_ASSIGNABLE,
    SUPER_ADMIN_PROTECTED,
    USER_NOT_FOUND,
    USERNAME_EXISTS,
)
from .model import User
from .schema import PasswordReset, RoleRef, UserCreate, UserInfo, UserUpdate


def _info(user: User, roles: list[RoleSummary]) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        is_disabled=user.is_disabled,
        roles=[
            RoleRef(id=role.id, name=role.name, code=role.code, is_disabled=role.is_disabled)
            for role in roles
        ],
    )


def _covers(actor: Identity, permissions: frozenset[str]) -> bool:
    return all(actor.can(item) for item in permissions)


async def _manageable(user_id: uuid.UUID, actor: Identity) -> tuple[User, list[RoleSummary]]:
    """取出要管理的對象, 並確認操作者有資格動他。"""
    user = found(await repository.get(user_id), USER_NOT_FOUND)
    roles = await get_roles(user.role_ids)
    # 停用的角色也算: 它日後可能恢復, 停用期間能動的帳號到時就成了提權。
    permissions = frozenset(item for role in roles for item in role.permissions)
    if WILDCARD in permissions:
        raise SUPER_ADMIN_PROTECTED()
    if not _covers(actor, permissions):
        raise CANNOT_MANAGE_HIGHER()
    return user, roles


async def _assignable_roles(role_ids: list[uuid.UUID], actor: Identity) -> list[RoleSummary]:
    roles = await get_roles(role_ids)
    if len(roles) != len(set(role_ids)) or any(
        role.is_disabled or role.is_super_admin for role in roles
    ):
        raise ROLE_NOT_ASSIGNABLE()
    if not all(_covers(actor, role.permissions) for role in roles):
        raise CANNOT_ASSIGN_HIGHER_ROLE()
    return roles


async def create_user(data: UserCreate, *, actor: Identity) -> UserInfo:
    roles = await _assignable_roles(data.role_ids, actor)
    if await repository.get_by_username(data.username):
        raise USERNAME_EXISTS()
    await release_connection()
    user = User(
        username=data.username,
        nickname=data.nickname,
        password_hash=await passwords.hash_password(data.password),
    )
    repository.set_roles(user, data.role_ids)
    try:
        await repository.add(user)
    except IntegrityError as error:
        # 事前的檢查擋下依序來的重複; 同時到的兩個請求由唯一約束接住。
        if is_unique_violation(error, "uq_users_username"):
            raise USERNAME_EXISTS() from error
        raise
    audit("user_created", user_id=user.id, role_ids=data.role_ids)
    return _info(user, roles)


async def get_user(user_id: uuid.UUID) -> UserInfo:
    user = found(await repository.get(user_id), USER_NOT_FOUND)
    return _info(user, await get_roles(user.role_ids))


async def list_users(
    params: PageParams,
    *,
    keyword: str | None,
    role_id: uuid.UUID | None,
    unassigned: bool,
    is_disabled: bool | None,
) -> Page[UserInfo]:
    result = await repository.page(
        params, keyword=keyword, role_id=role_id, unassigned=unassigned, is_disabled=is_disabled
    )
    # 整頁的角色一次查完, 查詢次數不隨筆數增加。
    roles = {
        role.id: role
        for role in await get_roles({i for user in result.items for i in user.role_ids})
    }
    return result.to_page(
        [_info(user, [roles[i] for i in user.role_ids if i in roles]) for user in result.items]
    )


async def update_user(user_id: uuid.UUID, data: UserUpdate, *, actor: Identity) -> UserInfo:
    user, roles = await _manageable(user_id, actor)
    roles_changed = set(data.role_ids) != set(user.role_ids)
    newly_disabled = data.is_disabled and not user.is_disabled
    if user.id == actor.id and (roles_changed or data.is_disabled):
        raise CANNOT_CHANGE_SELF()

    if roles_changed:
        # 只驗證這次新增的角色: 原本就有的 (即使後來被停用) 可以原樣保留。
        await _assignable_roles([i for i in data.role_ids if i not in user.role_ids], actor)
        repository.set_roles(user, data.role_ids)
        roles = await get_roles(data.role_ids)
    user.nickname = data.nickname
    user.is_disabled = data.is_disabled
    await db().flush()
    if newly_disabled:
        await repository.revoke_sessions(user.id)

    if newly_disabled:
        audit("user_disabled", user_id=user.id)
    if roles_changed:
        audit("user_roles_changed", user_id=user.id, role_ids=data.role_ids)
    return _info(user, roles)


async def disable_user(user_id: uuid.UUID, *, actor: Identity) -> UserInfo:
    user, roles = await _manageable(user_id, actor)
    if user.id == actor.id:
        raise CANNOT_CHANGE_SELF()
    if not user.is_disabled:
        user.is_disabled = True
        await db().flush()
        # 由資料庫遞增: 用讀到的舊值加一, 會蓋掉同一時間的登出或改密碼, 讓撤銷過的登入復活。
        await repository.revoke_sessions(user.id)
        audit("user_disabled", user_id=user.id)
    return _info(user, roles)


async def reset_password(user_id: uuid.UUID, data: PasswordReset, *, actor: Identity) -> None:
    user, _ = await _manageable(user_id, actor)
    await release_connection()
    password_hash = await passwords.hash_password(data.password)
    # 雜湊的幾百毫秒裡對方可能被升了權限, 寫入前用最新的資料再確認一次。
    db().expire(user)
    await _manageable(user_id, actor)
    await repository.set_password(user.id, password_hash)
    audit("user_password_reset", user_id=user.id)
