"""結構化 log: 正式環境一行一筆 JSON, 開發環境是好讀的彩色格式。

每一行自動帶上 `shared.context` 綁定的 request_id 與 user_id。時間一律 UTC。
用法: `log = get_logger(__name__)`, `log.info("role_created", role_id=...)`;
事件名稱用固定的英文代碼, 變動的值放欄位, 才搜得到也統計得了。
"""

import logging
import sys
from typing import Any

import structlog

from shared.settings import settings


def init_error_tracking(release: str) -> None:
    """設定了 SENTRY_DSN 才啟用 (Sentry 或相容的 GlitchTip)。error 等級以上的 log 會成為事件。

    不送使用者資料 (IP、cookie、請求內容): 送不送第三方是專案的決定, 預設不送。
    """
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.mode,
        release=f"{settings.project_name}@{release}",
        send_default_pii=False,
    )


def configure_logging(*, json_output: bool) -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json_output
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    # uvicorn、SQLAlchemy、alembic 用標準庫的 logging, 接到同一個輸出格式。
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *([structlog.processors.format_exc_info] if json_output else []),
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # 每個請求由平台的 middleware 記一筆, 不需要 uvicorn 再記一次。
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
