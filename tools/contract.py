"""前後端契約的產生。

    apps/api 的路由與 schema  →  contracts/openapi.json  →  apps/web/shared/api/schema.d.ts

兩份產出都進版控: 對外介面的變更在 review 的 diff 裡看得到。路徑只在這裡定義。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tools.env import REPO_ROOT

CONTRACT = REPO_ROOT / "contracts/openapi.json"
WEB_SCHEMA = REPO_ROOT / "apps/web/shared/api/schema.d.ts"

# 匯出契約只需要載入路由, 不連資料庫; 這組值只是讓設定通過檢查, 不會出現在產出裡。
EXPORT_ENV = {
    "PROJECT_NAME": "contract",
    "MODE": "development",
    "POSTGRES_URL": "postgresql+asyncpg://unused:unused@localhost/unused",
    "JWT_SECRET_KEY": "0" * 32,
    "EXPIRE_HOURS": "1",
}


def generate(contract: Path = CONTRACT, schema: Path = WEB_SCHEMA) -> None:
    result = subprocess.run(
        ["uv", "run", "--frozen", "python", "-m", "app.cli", "openapi"],
        cwd=REPO_ROOT / "apps/api",
        env={**os.environ, **EXPORT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(result.stdout, encoding="utf-8")
    subprocess.run(
        ["npx", "--no-install", "openapi-typescript", str(contract), "-o", str(schema)],
        cwd=REPO_ROOT / "apps/web",
        capture_output=True,
        check=True,
    )
