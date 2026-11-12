"""架構規則裡工具擋不到的部分。依賴方向由 import-linter 檢查 (pyproject.toml)。"""

import importlib
import inspect
from pathlib import Path

from shared.db.base import Base

API_ROOT = Path(__file__).resolve().parent.parent
MODULES = sorted(
    path.name for path in (API_ROOT / "modules").iterdir() if (path / "manifest.py").exists()
)


def test_there_are_no_horizontal_layers():
    # 功能要放在自己的模組裡; 一旦有了這些頂層套件, 一個功能就會散在各處。
    forbidden = {"api", "core", "services", "repositories", "models", "schemas", "utils"}
    assert not forbidden & {path.name for path in API_ROOT.iterdir() if path.is_dir()}


def test_public_entries_do_not_expose_tables():
    # 別的模組拿到資料表就能直接 JOIN, 模組的內部結構從此改不動。
    for name in MODULES:
        path = API_ROOT / "modules" / name / "public.py"
        if not path.exists():
            continue
        public = importlib.import_module(f"modules.{name}.public")
        exposed = [
            key
            for key, value in vars(public).items()
            if not key.startswith("_") and inspect.isclass(value) and issubclass(value, Base)
        ]
        assert not exposed, f"modules/{name}/public.py 轉出了資料表: {exposed}"


def test_every_module_is_shaped_the_same():
    for name in MODULES:
        manifest = importlib.import_module(f"modules.{name}.manifest")
        assert manifest.MODULE.name == name
