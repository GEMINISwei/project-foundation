"""這裡的 docstring 會進 OpenAPI 與前端型別檔, 只寫給呼叫端看的說明。"""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.permissions import Permission

RoleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class RoleCreate(BaseModel):
    name: RoleName
    permissions: list[Permission] = []


class RoleUpdate(BaseModel):
    name: RoleName
    permissions: list[Permission]
    is_disabled: bool


class RoleInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str | None
    name: str
    permissions: list[Permission]
    is_disabled: bool


class PermissionOption(BaseModel):
    """一個可以指派給角色的權限。畫面依 `category` 分組, 組內顯示 `label`。"""

    value: Permission
    label: str
    category: str
    requires: list[Permission]
