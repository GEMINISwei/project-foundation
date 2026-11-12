<!-- PR 標題用 Conventional Commits（`feat: add product list page`）：squash merge 後它就是 main 的 commit。
     先開 Draft，「驗證」寫完再按 Ready for review。流程見 docs/foundation/workflow.md#開發流程 -->

## 摘要

<!-- 這個 PR 改了哪些內容、為什麼。之後再推 commit 時回來補，讓這段一直對得上最新的 diff。 -->

-

## 驗證

<!-- 做過哪些驗證、結果如何，成功與失敗都寫；沒驗到的寫原因。
     驗收條件一條一行，接測試名稱與結果。寫不出測試名稱，代表那一條還沒想清楚。
     AI agent 寫的驗收條件，先給使用者確認才開始寫測試。
     實作開始之後改過的測試檔，在這一段寫一行：路徑與原因寫在同一行。
- 管理者不能停用自己的帳號 → `test_cannot_disable_self`：通過
- CI：通過
     依改動補上：schema／權限／語系 → `make gen-types`；model → `make db migration "說明"`；
     新增模組 → 前後端的 `ENABLED_MODULES` -->

-

## 檢查

<!-- 請審查者確認的項目。整份 diff 本來就要看，不用列；這裡寫 diff 看不出來、需要人去確認的事，
     例如在部署主機實際跑一次、對已部署的下游有沒有影響、畫面在手機寬度下的樣子。
     動到防線檔案、AGENTS.md 或 skills 時，說明會不會讓檢查變寬鬆（檔案清單在 diff 裡看得到，不用另外列）。
     改到模組的 public entry（後端 `public.py`、前端 `public.server.ts`／`public.client.ts`）時列一項：
     新增的是有意義的能力，不是把內部原封不動轉出（檢查擋不到這種情況，見 docs/foundation/architecture.md〈模組之間的資料關聯〉）。 -->

- [ ]
