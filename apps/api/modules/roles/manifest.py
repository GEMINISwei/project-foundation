from shared.module import ModuleManifest

from .model import Role
from .permissions import PERMISSIONS
from .router import router
from .seed import seed_system_roles

MODULE = ModuleManifest(
    name="roles",
    routers=(router,),
    models=(Role,),
    permissions=PERMISSIONS,
    seeders=(seed_system_roles,),
)
