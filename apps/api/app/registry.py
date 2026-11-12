"""啟用中的模組。啟用或停用一個模組只改這裡 (以及 `app/permissions.py` 裡它的權限值)。"""

from modules.roles.manifest import MODULE as ROLES
from modules.users.manifest import MODULE as USERS
from shared.module import ModuleManifest, validate_modules

ENABLED_MODULES: tuple[ModuleManifest, ...] = validate_modules((USERS, ROLES))
