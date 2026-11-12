"""api 的進入點: python -m app.api"""

import uvicorn

from shared.settings import settings

if __name__ == "__main__":
    development = not settings.is_production
    uvicorn.run(
        "app.server:app",
        # 容器裡要綁 0.0.0.0 才能被 compose 內網的 web 連到; 對外只有 nginx 的 port。
        host="0.0.0.0",  # noqa: S104
        port=8000,
        # reload 與多行程不能並用; 開發環境固定單一行程。
        reload=development,
        workers=None if development else settings.api_workers,
        # log 的格式由 shared/logging.py 統一設定, 請求紀錄由平台的 middleware 負責。
        log_config=None,
        access_log=False,
        # 收到 SIGTERM 後等進行中的請求做完, 上限要小於 compose 的 stop_grace_period。
        timeout_graceful_shutdown=25,
    )
