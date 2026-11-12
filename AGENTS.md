# 給 AI agent 的專案指引

這是給 AI agent 的**唯一**指引（Claude 與 Codex 共用，不另設 `CLAUDE.md`）。只寫無法從程式碼推導的規則，細節見：
[`architecture.md`](docs/foundation/architecture.md)（分層、模組介面、前後台、權限）、
[`development.md`](docs/foundation/development.md)（環境、指令、風格）、
[`testing.md`](docs/foundation/testing.md)（測試策略、驗收條件）、
[`workflow.md`](docs/foundation/workflow.md)（開發流程、提交、相依升級）、
[`operations.md`](docs/foundation/operations.md)（部署、發版、備份、排查）、
[`new-module.md`](docs/foundation/new-module.md)、[`permissions.md`](docs/foundation/permissions.md)、
[`migrations.md`](docs/foundation/migrations.md)、[`jobs.md`](docs/foundation/jobs.md)（新增模組、權限、migration、背景任務）、
[`hooks-and-skills.md`](docs/foundation/hooks-and-skills.md)（hooks 與 skills）、
[`decisions.md`](docs/foundation/decisions.md)（刻意不採用主流做法的地方）。
提議改掉某個做法之前，先讀 `decisions.md` 的那一條。

`docs/foundation/` 是骨架帶來的文件；專案自己的在 [`docs/project/`](docs/project/README.md)。
**先讀 `docs/project/`，兩邊寫的不一樣時以它為準。**

## 硬規則（CI 會擋）

1. **依賴只能往一個方向**：`app → modules → shared`。`shared` 不引用 `modules` 或組裝層。
2. **跨模組只走 public entry**：後端 `public.py`，前端 `public.server.ts`／`public.client.ts`。組裝層也一樣。
   public 只轉出函式與回傳型別，不轉出資料表。
3. **後端不開水平分層的目錄**（`services/`、`repositories/`、`utils/`）；前端模組不開 `components/`、`hooks/`、`utils/`，
   畫面放 `ui/`，其餘放模組根。
4. **後端錯誤一律 `ErrorSpec`**（帶錯誤代碼與雙語訊息），不用裸的 `HTTPException`。
5. **後端 service 回傳 schema**，不回傳資料表物件；所有函式都要有型別註記（mypy 嚴格模式）。
6. **前端模組內部用相對路徑**，`@/` 只用於跨層；UI 元件只從 `@/shared/ui` 匯入。
7. **路由檔（`app/**/page.tsx`）只做轉接，而且要逐一轉接 Next 特有的 export**（`generateMetadata` 等）。
8. **後台頁面的路徑以 `/admin/` 開頭並宣告權限；前台頁面不可以用 `/admin/`**。頁面在模組的 manifest 宣告，
   並把 manifest 加進 `config/routes.ts`。
9. **使用者看得到的字串都要中英兩份**：前端在擁有它那一層的 `i18n.ts`，後端用 `LangText`。
10. **權限值加進 `app/permissions.py` 之後一定要有模組宣告它**（標籤、分類、相依）；命名 `資源:動作`。
11. **改了後端的 schema、路由、權限或語系要 `make gen-types`**，兩份產出一起 commit。
12. **已經發版的 migration 不可修改或刪除**；model 與 migration 要一致。
13. **新增的抑制註解同一行要寫理由**（`# noqa`、`# type: ignore`、`eslint-disable`、跳過測試）。
14. **skills 只放 `.agents/skills/`，hook 的邏輯只放 `.agents/hooks/`**，兩家的設定要一致。

## 漏了不會報錯的地方

沒辦法寫成檢查的才列在這裡。

- **瀏覽器不直接呼叫後端**。要從畫面寫入時，在模組的 `actions.ts` 包一層具名、窄介面的 Server Action；
  不要在 nginx 或 Next 加 `/api/` 的轉送，也不要在 `shared/api/client.server.ts` 加 `"use server"`。
- **Server Action 的回傳值會送進瀏覽器**：寫入登入 cookie 的 action 回傳前要經過 `withoutData`。
- **不用 `NEXT_PUBLIC_*` 放設定**（建置時就固定了），執行期設定走 `shared/runtime/`。
- **`apps/web/proxy.ts` 留在原位**：放錯位置 Next 照樣建置成功，路由保護卻整層消失。
- **畫面上的權限判斷只是體驗**，每個後端端點都要用 `require(...)` 宣告權限。
- **後台的寫入要守住三條防提權的規則**（不授予自己沒有的權限、不管理權限比自己高的帳號、不改自己的角色與狀態），
  新增會改到帳號或角色的功能時比照 `modules/users/service.py`。
- **AUDIT、log 與任務的 payload 只放 id 與固定的代碼**，不放帳號、暱稱或使用者輸入的內容。
- **背景任務必須能重跑**；任務名稱不要改。
- **上傳的檔案存在 `/app/uploads/<模組>/`**：存到別的路徑，重建容器就消失，也備份不到。
- **schema、路由函式與 enum 的 docstring 會進公開的 API 契約**，內部說明寫在一般註解。
- **主機的 reverse proxy 在 repo 之外**：它要覆寫 `X-Real-IP` 與 `X-Forwarded-Proto`，少了不會報錯
  （[說明](docs/foundation/operations.md#主機的-reverse-proxy)）。
- **compose 的旗標不要自己組**，一律經過 `tools/compose.py`。
- **`docs/foundation/` 與基礎建設歸 foundation**（[檔案歸誰](docs/foundation/workflow.md#檔案歸誰)）：在子專案裡改了，
  下次同步就會衝突。專案自己的說明與決定寫在 `docs/project/`，基礎建設的修正先回到 foundation。

## 高風險先問

檢查擋不完所有寫法，hook 只擋常見的那幾種。下列情況先停下來說明要做什麼、為什麼，等使用者同意；
沒列到但你判斷同樣危險的，也照辦：

- 不可逆或影響 repo 以外的動作：部署、發布、合併、刪資料或分支、動主機、改別的 repo、送出外部服務
- 改防線檔案（hook、agent 設定、CI、檢查的設定與入口）
- 實作開始後改測試、放寬斷言、加抑制註解或跳過測試
- 超出驗收條件的範圍
- 升級相依：先在乾淨的環境實際安裝並跑過檢查，確認整組相容；有不相容的要告知並提出替代方案
- 想換個寫法避開被 hook 或檢查擋下的動作

被 hook 擋下時照它給的理由做。**測試檔與防線檔案**：在對話訊息裡一次列出所有要改的檔案，每個寫原因與怎麼改
（簡短即可），**最後才問一句是否全部同意**。清單不要塞進詢問視窗：項目一多會顯示不完，使用者看不到就無法判斷。
同意後執行一次 `python3 .agents/hooks/approve.py <test|protected> <檔案…>`
（[說明](docs/foundation/hooks-and-skills.md#測試鎖)）。

## 寫程式

- **流程：Feature Branch → Draft PR → Incremental Commits → Code Review → Squash Merge**。不直接 push `main`；
  PR 標題用 Conventional Commits。照 `feature-workflow` skill 做。
- **一次只有一個進行中的 PR**；要插隊照 `hotfix` skill 先問使用者。
- **PR 描述固定三段：摘要、驗證、檢查**。`gh pr create --body` 會跳過模板，自己帶內文時也照這三段。
- **每個 commit 最後加 `Co-authored-by: <產品> <模型與版本> <email>`**，不用 `--no-verify` 繞過檢查。
- **動手前把驗收條件寫進 Draft PR 的「驗證」段，每條對應一個測試名稱，列給使用者確認之後才開始寫測試**。
- **先寫測試，寫好才開始實作**；測試變紅時預設它是對的，改實作讓它變綠。
- **測試放該 app 的 `tests/`，與原始碼同構**。`actions.ts` 與 `ui/*.tsx` 不寫執行期測試，
  畫面的分支抽進 `capabilities.ts` 再測。不要為了覆蓋率數字補測試。
- **程式碼要簡潔**：不加用不到的抽象、設定或參數；少量重複不急著抽成共用。
- **註解寫為什麼，不寫做了什麼**；程式碼裡的註解用半形標點，字串與 Markdown 用全形。
- **CSS 只用設計變數**，不寫死色值或尺寸。
- 一個任務交給一個 agent；不要兩個 agent 同時改同一個分支。

## 改完之後

| 改了什麼 | 要做 |
|---|---|
| 任何程式碼 | push，照 `watch-pr` 等 CI。完整的檢查只在 CI 跑；寫測試時只跑那一項確認紅燈 |
| model 的欄位、索引、約束 | 照 `add-migration`：`make db migration "說明"`，讀過產出 |
| 跟資料庫互動的後端程式 | `make check integration <測試檔>` |
| 登入、導向、權限、cookie | `make e2e up` 後 `make e2e test <檔案>` |
| 後端的 schema、路由、權限、語系 | `make gen-types` |
| 環境變數 | `.env.example`、`infra/compose/compose.yml`、讀取端（[說明](docs/foundation/development.md#環境變數)） |
| nginx 模板 | 每個轉送的 location 都要 `include` `snippets/proxy-headers.conf` |
| 發版 | `release` skill；不要手動改版號 |
| 行為有變 | `CHANGELOG.md` 的 `[Unreleased]` 留一筆（foundation 本身例外，見下面） |
| 要帶進 foundation 的更新 | `sync-foundation` skill；不要手動複製檔案 |

## 只適用於 foundation 本身

根目錄**沒有** `.foundation.json` 的 repo 才是 foundation 本身，下面兩條只管它。
**用這份骨架建立的專案不受限制**：要記錄演進、寫升級說明、維護 CHANGELOG，都照專案自己的需要。

- **只寫現況，不寫演進**：文件、註解、skill 與 hook 的提示都不寫「原本…現在…」「已改為…」這類敘述，
  也不寫升級步驟；做法變了就直接改寫成現在的樣子（[理由](docs/foundation/workflow.md#foundation-只寫現況)）。
- **不寫 `CHANGELOG.md`**：那一份留給專案記自己的版本。

## 本專案的規則

用這份骨架建立的專案只在這一段加自己的規則，前面的段落跟著 foundation，不改。
