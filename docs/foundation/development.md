# 開發指南

## 開發環境

需要 Docker（Compose v2.24 以上）、`make`、`python3`（3.9 以上，`make` 指令與 agent 的 hook 用）、
`uv`（0.13 以上）與 Node（版本見 `apps/web/.nvmrc`）。

```bash
make init dev   # 產生 .env、安裝三處的相依 (apps/api、apps/web、e2e)、啟用 git hook
make start      # 啟動 postgres → migrate → api、worker → web → nginx
make db superuser
```

- 開發環境的原始碼是 bind mount，改了直接生效；改了相依（`pyproject.toml`、`package.json`）要重新 `make start`。
- `make start lan` 把 port 對區網開放，讓手機連進來測試；下一次 `make start` 就關回只限本機。
- 服務跑在容器裡，檢查與測試跑在主機上（編輯器與 CI 看到的就是這個環境）。

### 起不來的時候

```bash
make doctor          # 一次列出版本、設定、各服務狀態的問題
make status          # 各容器的狀態
make logs api        # 看某個服務的 log
```

`migrate` 失敗時 api 與 worker 不會啟動，原因在 `make logs migrate`。

### 環境變數

清單與說明在 [`.env.example`](../../.env.example)，`make init` 依它產生 `.env`。新增一個變數要改三處：

1. `.env.example`：加上變數與上一行的說明。
2. `infra/compose/compose.yml`：傳進需要它的服務。
3. 讀取端：後端 `shared/settings.py`（缺少或不合法時啟動就失敗），前端 `shared/runtime/`。

要自動產生的祕密另外加進 `tools/commands/init.py` 的 `GENERATED`。`make doctor` 會提醒 `.env` 缺了哪些變數。
已經部署的主機不會自動多出新變數：需要時在主機的 `.env` 補上，再照
[套用 `.env` 的變更](operations.md#套用-env-的變更)重新部署。

## 指令

`make help` 列出全部，`make <指令> help` 看子指令。實作在 `tools/`（Python 標準函式庫）。

| 指令 | 用途 |
|---|---|
| `make init dev\|prod` | 產生 `.env`、檢查環境；`dev` 另外安裝相依 |
| `make start`、`make stop`、`make status` | 啟動、停止、狀態 |
| `make logs [服務]`、`make logs trace <id>`、`make logs errors [分鐘]` | 看 log、追一次請求、列出最近的錯誤 |
| `make doctor` | 檢查這台機器與執行中的服務 |
| `make db psql\|superuser\|revoke-sessions\|migration\|reset` | 資料庫與帳號 |
| `make jobs list\|retry\|run` | 背景任務 |
| `make backup`、`make backup restore db\|uploads` | 備份與還原 |
| `make check <項目>` | 檢查與測試的單項（完整的檢查在 CI） |
| `make e2e up\|test\|grep\|down\|check` | 瀏覽器測試 |
| `make gen-types` | 重新產生契約與前端型別 |
| `make release <版號>` | 準備發版 |

改完之後要做什麼：

| 改了什麼 | 要做 |
|---|---|
| 後端的 schema、路由、權限、語系 | `make gen-types`，兩份產出一起 commit |
| model 的欄位、索引、約束 | `make db migration "說明"`，讀過產出 |
| 登入、導向、權限、cookie | `make e2e up` 後 `make e2e test <檔案>` |
| 行為有變 | `CHANGELOG.md` 的 `[Unreleased]` 留一筆 |

## 程式碼風格

- **後端**：`ruff check` 與 `ruff format`（行寬 100）、mypy 嚴格模式、import-linter。
- **前端**：ESLint（行寬 100、函式長度與複雜度有上限）、`tsc`、dependency-cruiser、knip（不留未使用的匯出）。
- 函式長度與複雜度的上限是防退步的地板，擋「長到沒人敢動」，不是逼人拆碎。

### 註解與文件

- 註解寫**為什麼**，不寫做了什麼；看程式碼就知道的不寫。演進過程寫進 commit 訊息。
- 程式碼裡的註解與 docstring 用半形標點（`, : ; ( )`）；字串與 Markdown 維持全形。
- 事件名稱（log 的 `event`、AUDIT 的事件、錯誤代碼）用固定的英文代碼，變動的值放欄位。

### 抑制註解

`# noqa`、`# type: ignore`、`eslint-disable`、`@ts-expect-error`、跳過測試，**同一行要寫理由**：

```python
token_type: str = "bearer"  # noqa: S105 — 憑證的種類, 不是密碼
```

CI 的 `pr` 會檢查這個 PR 新增的抑制註解（`.github/scripts/check-pr-changes.py`）。

### 相依版本

- 後端正式環境的相依一律 `==`；開發用的用 `>=`，實際版本由 `uv.lock` 固定。
- 升 Python 要同時改四處：`pyproject.toml` 的 `requires-python`、ruff 的 `target-version`、mypy 的
  `python_version`、`Dockerfile` 的 `FROM`，再重新產生 `uv.lock`。
- 升 Node 要同時改三處：`.nvmrc`、`package.json` 的 `engines`、`Dockerfile` 的 `NODE_VERSION`。
- TypeScript 停在 5.9：`openapi-typescript` 與 `typescript-eslint` 還不支援更新的版本，
  升級條件寫在 `apps/web/package.json` 的 `//devDependencies`。
