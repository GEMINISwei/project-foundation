"""角色的業務規則。

- 系統角色 (有 code 的) 由初始資料擁有, 後台不能改也不能停用。
- 儲存時自動補上相依的權限, 所以資料庫裡的集合永遠完整。
- 非超級管理者不能授予自己沒有的權限, 否則拿到 `roles:write` 就能替自己提權。
- 非超級管理者只能動權限不超過自己的角色: 改名、停用、重新啟用都算。否則可以把別人停用的
  高權限角色開回來 (間接提權), 或把比自己高的角色停掉、拔權限 (越權撤權)。
"""

import uuid

from sqlalchemy.exc import IntegrityError

from app.permissions import Permission
from shared.audit import audit
from shared.auth.identity import Identity
from shared.auth.permissions import PermissionCatalog
from shared.db.integrity import is_unique_violation
from shared.db.pagination import ItemList, Page, PageParams
from shared.db.session import db
from shared.errors import found

from . import repository
from .errors import (
    CANNOT_GRANT_UNOWNED,
    CANNOT_MANAGE_HIGHER,
    ROLE_NAME_EXISTS,
    ROLE_NOT_FOUND,
    SYSTEM_ROLE_READONLY,
    WILDCARD_NOT_ASSIGNABLE,
)
from .model import Role
from .schema import PermissionOption, RoleCreate, RoleInfo, RoleUpdate


def _resolve_permissions(
    requested: list[Permission], *, actor: Identity, catalog: PermissionCatalog
) -> list[str]:
    """驗證並補齊要存進角色的權限。"""
    if Permission.ALL in requested:
        raise WILDCARD_NOT_ASSIGNABLE()
    completed = catalog.complete(requested)
    if not all(actor.can(item) for item in completed):
        raise CANNOT_GRANT_UNOWNED()
    return completed


async def _manageable(role_id: uuid.UUID, actor: Identity) -> Role:
    """取出要修改的角色, 並確認操作者有資格動它。"""
    role = found(await repository.get(role_id), ROLE_NOT_FOUND)
    if role.is_system:
        raise SYSTEM_ROLE_READONLY()
    if not all(actor.can(item) for item in role.permissions):
        raise CANNOT_MANAGE_HIGHER()
    return role


async def _flush_unique_name() -> None:
    # 事前的檢查擋下依序來的重複; 同時到的兩個請求由唯一約束接住。
    try:
        await db().flush()
    except IntegrityError as error:
        if is_unique_violation(error, "uq_roles_name"):
            raise ROLE_NAME_EXISTS() from error
        raise


async def create_role(data: RoleCreate, *, actor: Identity, catalog: PermissionCatalog) -> RoleInfo:
    permissions = _resolve_permissions(data.permissions, actor=actor, catalog=catalog)
    if await repository.name_taken(data.name):
        raise ROLE_NAME_EXISTS()
    role = Role(name=data.name, permissions=permissions)
    db().add(role)
    await _flush_unique_name()
    audit("role_created", role_id=role.id, permissions=permissions)
    return RoleInfo.model_validate(role)


async def get_role(role_id: uuid.UUID) -> RoleInfo:
    return RoleInfo.model_validate(found(await repository.get(role_id), ROLE_NOT_FOUND))


async def list_roles(
    params: PageParams, *, name: str | None, is_disabled: bool | None
) -> Page[RoleInfo]:
    result = await repository.page(params, name=name, is_disabled=is_disabled)
    return result.to_page([RoleInfo.model_validate(role) for role in result.items])


async def list_role_options(*, is_disabled: bool | None) -> ItemList[RoleInfo]:
    roles = await repository.list_all(is_disabled=is_disabled)
    return ItemList(items=[RoleInfo.model_validate(role) for role in roles])


def list_permission_options(catalog: PermissionCatalog) -> ItemList[PermissionOption]:
    return ItemList(
        items=[
            PermissionOption(
                value=Permission(spec.value),
                label=spec.label.resolve(),
                category=spec.category.resolve(),
                requires=sorted(Permission(item) for item in spec.requires),
            )
            for spec in catalog.specs
        ]
    )


async def update_role(
    role_id: uuid.UUID, data: RoleUpdate, *, actor: Identity, catalog: PermissionCatalog
) -> RoleInfo:
    role = await _manageable(role_id, actor)
    permissions = _resolve_permissions(data.permissions, actor=actor, catalog=catalog)
    if await repository.name_taken(data.name, except_id=role.id):
        raise ROLE_NAME_EXISTS()
    role.name = data.name
    role.permissions = permissions
    role.is_disabled = data.is_disabled
    await _flush_unique_name()
    audit("role_updated", role_id=role.id, permissions=permissions, is_disabled=role.is_disabled)
    return RoleInfo.model_validate(role)


async def disable_role(role_id: uuid.UUID, *, actor: Identity) -> RoleInfo:
    role = await _manageable(role_id, actor)
    role.is_disabled = True
    await db().flush()
    audit("role_disabled", role_id=role.id)
    return RoleInfo.model_validate(role)
