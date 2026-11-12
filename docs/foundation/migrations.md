# Migration

改了 model 的欄位、索引或約束之後：

```bash
make db migration "add product price"   # 需要開發環境在執行 (make start)
```

產生的檔案在 `apps/api/migrations/versions/`。下一次 `make start`（或部署）時由 migrate 服務套用。

## 注意事項

自動產生的內容**一定要自己讀一遍**，它固定會漏三件事：

- **資料**：往有資料的表加 `NOT NULL` 欄位，它只寫 `ADD COLUMN`，不會回填。要分三步：加可為空的欄位、回填、再設成 `NOT NULL`。
- **改名**：欄位或表改名會被看成刪一個、加一個，照著跑資料就沒了。改成 `op.alter_column(..., new_column_name=...)`。
- **不能在交易裡執行的 DDL**（`CREATE INDEX CONCURRENTLY`）：大表加索引時要另外處理。

其他規則：

- **migration 只往前**。`downgrade()` 留著自動產生的內容即可，部署流程不會執行它。
- **已經發版的 migration 不能修改或刪除**（CI 的 `migrations` 會擋），要改結構就新增一支。
- model 與 migration 不一致時 CI 的 `api-integration` 會失敗。
- 新增的資料表要列在模組 manifest 的 `models`，否則 migration 看不到它。
- 資料表與約束的名稱由 `shared/db/base.py` 的命名規則決定，不要手動取名。

## 發版之前可以整理

最近一個 `v*` tag 之後才新增的 migration 還沒跑在任何主機上：同一個功能的可以併成一支，
改完 `make db reset` 重建開發資料庫。

## 初始資料

需要「系統一啟動就該存在」的資料時（系統角色），在模組寫一個可以重複執行的函式，放進 manifest 的 `seeders`
（例：`modules/roles/seed.py`）。它在每次 migrate 之後執行：存在就更新，不存在才新增。
不要寫成資料 migration：那種寫法發版後就不能改，也不能 import model。

## 回滾

兩版之間多了 migration 就不能回滾到舊版（[說明](operations.md#回滾與-migration)）。
PR 有 migration 時在「檢查」段提醒這件事。
