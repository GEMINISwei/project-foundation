"""系統角色。每次 migrate 都同步回這裡的定義, 所以資料庫裡對系統角色的改動會被蓋回來。"""

from app.permissions import Permission

from . import repository
from .model import SUPER_ADMIN_CODE, Role

_SYSTEM_ROLES = ((SUPER_ADMIN_CODE, "Super Admin", [Permission.ALL.value]),)


async def seed_system_roles() -> None:
    for code, name, permissions in _SYSTEM_ROLES:
        role = await repository.get_by_code(code)
        if role is None:
            await repository.add(Role(code=code, name=name, permissions=permissions))
        else:
            role.name, role.permissions, role.is_disabled = name, permissions, False
