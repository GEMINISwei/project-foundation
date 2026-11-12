"""平台的環境設定。缺少或不合法時在啟動當下就失敗, 並列出是哪幾項。

模組自己的設定另外定義自己的 `BaseSettings`, 不加進這裡。
"""

import sys
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 必填: 不給預設值, 缺少時不能安靜地用一組不安全的值啟動 ──
    project_name: str = Field(min_length=1)
    # 裸的 `postgresql://` 會變成看不出原因的 `ModuleNotFoundError: psycopg2`。
    postgres_url: str = Field(pattern=r"^postgresql\+asyncpg://")
    jwt_secret_key: str = Field(min_length=32)
    # 前端用同一個值算 cookie 的 maxAge, 兩邊必須一致。
    expire_hours: int = Field(ge=1)

    # ── 選填 ──
    mode: Literal["development", "production"] = "development"
    # 排程的時區。log 與資料庫一律 UTC。
    timezone: str = "Asia/Taipei"
    api_workers: int = Field(default=1, ge=1)
    sentry_dsn: str = ""

    # 連線池: 每個行程 (api 的每個 worker、worker 容器) 各一份。
    # 上限要讓所有行程加起來不超過 PostgreSQL 的 max_connections (預設 100)。
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    # 單一查詢的時間上限: 一個失控的查詢不能佔住連線到天荒地老。
    db_statement_timeout_ms: int = Field(default=30_000, ge=1)

    # worker 多久查一次有沒有到期的任務。
    job_poll_seconds: float = Field(default=5, gt=0)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"不是有效的 IANA 時區名稱: {value}") from error
        return value

    @property
    def is_production(self) -> bool:
        return self.mode == "production"


def _load() -> Settings:
    try:
        return Settings()  # 必填欄位由環境變數帶入
    except ValidationError as error:
        details = "\n".join(
            f"  - {'.'.join(str(part) for part in item['loc']).upper()}: {item['msg']}"
            for item in error.errors()
        )
        print(f"環境變數設定錯誤，服務無法啟動：\n{details}", file=sys.stderr)
        raise SystemExit(1) from error


settings = _load()
