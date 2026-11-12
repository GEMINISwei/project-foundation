from shared.module import ModuleManifest

from .identity import load_identity
from .model import User, UserRole
from .permissions import PERMISSIONS
from .router import router

MODULE = ModuleManifest(
    name="users",
    routers=(router,),
    models=(User, UserRole),
    permissions=PERMISSIONS,
    identity_loader=load_identity,
)
