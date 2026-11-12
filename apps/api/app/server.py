"""組裝出這個專案的 app。平台接線在 `shared/platform.py`。"""

from fastapi import FastAPI

from app.permissions import Permission
from app.registry import ENABLED_MODULES
from app.version import APP_VERSION
from shared.module import ModuleManifest
from shared.platform import create_platform_app


def create_app(modules: tuple[ModuleManifest, ...] = ENABLED_MODULES) -> FastAPI:
    return create_platform_app(modules=modules, permissions=Permission, app_version=APP_VERSION)


app = create_app()
