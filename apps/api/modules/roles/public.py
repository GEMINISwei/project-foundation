"""roles 模組對外的介面。其他模組只能 import 這個檔案。

只轉出函式與它們的回傳型別, 不轉出資料表: 別的模組以 id 參照角色 (外鍵用字串宣告
`ForeignKey("roles.id")`), 要角色的內容就呼叫這裡。
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from shared.errors import found

from . import repository
from .errors import ROLE_NOT_FOUND
from .model import SUPER_ADMIN_CODE


@dataclass(frozen=True)
class RoleSummary:
    id: uuid.UUID
    name: str
    code: str | None
    permissions: frozenset[str]
    is_disabled: bool

    @property
    def is_super_admin(self) -> bool:
        return self.code == SUPER_ADMIN_CODE


async def get_roles(role_ids: Iterable[uuid.UUID]) -> list[RoleSummary]:
    """批次取得角色; 不存在的 id 不會出現在結果裡。"""
    return [
        RoleSummary(role.id, role.name, role.code, frozenset(role.permissions), role.is_disabled)
        for role in await repository.get_many(role_ids)
    ]


async def get_super_admin_role_id() -> uuid.UUID:
    return found(await repository.get_by_code(SUPER_ADMIN_CODE), ROLE_NOT_FOUND).id


def effective_permissions(roles: Iterable[RoleSummary]) -> frozenset[str]:
    """一組角色合起來的權限; 停用的角色不算。"""
    return frozenset(item for role in roles if not role.is_disabled for item in role.permissions)
