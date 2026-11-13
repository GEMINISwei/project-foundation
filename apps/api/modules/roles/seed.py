"""系統角色。每次 migrate 都同步回這裡的定義, 所以資料庫裡對系統角色的改動會被蓋回來。"""

from app.permissions import Permission
from shared.logging import get_logger

from . import repository
from .model import SUPER_ADMIN_CODE, Role

log = get_logger(__name__)

_SYSTEM_ROLES = ((SUPER_ADMIN_CODE, "Super Admin", [Permission.ALL.value]),)


async def seed_system_roles() -> None:
    for code, name, permissions in _SYSTEM_ROLES:
        role = await repository.get_by_code(code)
        if role is None:
            await repository.add(Role(code=code, name=name, permissions=permissions))
        else:
            role.name, role.permissions, role.is_disabled = name, permissions, False


async def drop_removed_permissions() -> None:
    """清掉角色裡 enum 已經沒有的權限值 (模組被移除、權限改名之後留下的)。

    留著的話, 把它轉回 enum 的地方 (登入者的權限、角色列表) 會直接丟錯, 持有那個角色的人
    每個請求都是 500。移除權限一定伴隨一次部署, 所以在這裡清一次就不必到處容錯。
    """
    known = {permission.value for permission in Permission}
    for role in await repository.list_all(is_disabled=None):
        kept = [item for item in role.permissions if item in known]
        if kept != role.permissions:
            log.warning(
                "role_permissions_dropped",
                role_id=str(role.id),
                removed=sorted(set(role.permissions) - known),
            )
            role.permissions = kept
