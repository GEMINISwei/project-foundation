---
name: add-migration
description: 改了後端 model 的欄位、索引或約束，要新增或整理 Alembic migration 時使用。
---

# 新增 migration

說明在 [`migrations.md`](../../../docs/foundation/migrations.md)。

1. **能不能併進既有的**：找最近的 `v*` tag（含 prerelease，`git describe --tags --abbrev=0 --match 'v*'`）。
   tag 之前的只能往前，不可改或刪；tag 之後同一個功能的可以併成一支，改完 `make db reset`；沒有 tag 就都還沒發版。
2. **產生**：`make db migration "說明"`。
3. **讀過產出**：autogenerate 固定會漏 NOT NULL 欄位的預設或回填、改名被當成刪除加新增、不能在交易裡跑的 DDL，
   照 [注意事項](../../../docs/foundation/migrations.md#注意事項) 補上。
4. **檢查**：push 後由 CI 的 `api-integration`（model 與 migration 一致）與 `migrations`（已發版的沒被改動）檢查。
5. **schema 有變**：`make gen-types`，兩份產出一起 commit。
6. PR「檢查」段提醒：兩版之間多了 migration 就不能回滾（[說明](../../../docs/foundation/operations.md#回滾與-migration)）。
