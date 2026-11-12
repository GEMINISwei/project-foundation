import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.permissions import Permission
from shared.auth.identity import Identity, require
from shared.auth.permissions import PermissionCatalog, get_catalog
from shared.db.pagination import ItemList, Page, PageParams

from . import service
from .schema import PermissionOption, RoleCreate, RoleInfo, RoleUpdate

router = APIRouter(prefix="/roles", tags=["roles"])

Catalog = Annotated[PermissionCatalog, Depends(get_catalog)]
Reader = Annotated[Identity, Depends(require(Permission.ROLES_READ))]
Writer = Annotated[Identity, Depends(require(Permission.ROLES_WRITE))]


@router.get("")
async def list_roles(
    _: Reader,
    params: Annotated[PageParams, Query()],
    name: str | None = None,
    is_disabled: bool | None = None,
) -> Page[RoleInfo]:
    return await service.list_roles(params, name=name, is_disabled=is_disabled)


# 這兩條要在 `/{role_id}` 之前, 否則 "options" 會先被當成 id。
@router.get("/options")
async def list_role_options(_: Reader, is_disabled: bool | None = None) -> ItemList[RoleInfo]:
    """不分頁的完整角色清單, 給下拉選單用。"""
    return await service.list_role_options(is_disabled=is_disabled)


@router.get("/permission-options")
async def list_permission_options(_: Reader, catalog: Catalog) -> ItemList[PermissionOption]:
    """角色可以勾選的權限, 標籤與分類是目前語系的文字。"""
    return service.list_permission_options(catalog)


@router.post("", status_code=201)
async def create_role(data: RoleCreate, actor: Writer, catalog: Catalog) -> RoleInfo:
    return await service.create_role(data, actor=actor, catalog=catalog)


@router.get("/{role_id}")
async def get_role(role_id: uuid.UUID, _: Reader) -> RoleInfo:
    return await service.get_role(role_id)


@router.put("/{role_id}")
async def update_role(
    role_id: uuid.UUID, data: RoleUpdate, actor: Writer, catalog: Catalog
) -> RoleInfo:
    return await service.update_role(role_id, data, actor=actor, catalog=catalog)


@router.post("/{role_id}/disable")
async def disable_role(role_id: uuid.UUID, actor: Writer) -> RoleInfo:
    """停用角色。角色被使用者參照著, 所以沒有真的刪除。"""
    return await service.disable_role(role_id, actor=actor)
