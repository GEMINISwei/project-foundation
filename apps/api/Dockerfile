FROM python:3.15-slim

# 容器維持 UTC: log 與資料庫只認 UTC, 當地時間由瀏覽器與排程的 TIMEZONE 設定處理。

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-cache

# 逐一列出而不是 `COPY . .`: tests/ 與雜物不進正式 image。
COPY alembic.ini ./
COPY app/ ./app/
COPY modules/ ./modules/
COPY shared/ ./shared/
COPY migrations/ ./migrations/

# 以非 root 執行。uploads 要在 chown 之前建好: 新的具名 volume 沿用 image 裡這個目錄的擁有者。
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --no-create-home app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app

USER app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "app.api"]
