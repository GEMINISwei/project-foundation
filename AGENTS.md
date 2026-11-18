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
15. **每條 API 路由都宣告權限**：用 `require(...)`，不需要登入的標 `dependencies=[Depends(public())]`；
    E2E 的 spec 一律從 `support` 匯入 `test`（[執行期契約](docs/foundation/testing.md#執行期契約)）。

## 漏了不會報錯的地方

沒辦法寫成檢查的才列在這裡。

- **瀏覽器不直接呼叫後端**。要從畫面寫入時，在模組的 `actions.ts` 包一層具名、窄介面的 Server Action；
  不要在 nginx 或 Next 加 `/api/` 的轉送，也不要在 `shared/api/client.server.ts` 加 `"use server"`。
  E2E 抓得到瀏覽器打 `/api/` 的請求，抓不到換了路徑的轉送。
- **Server Action 的回傳值會送進瀏覽器**：寫入登入 cookie 的 action 回傳前要經過 `withoutData`。
  E2E 走過的 action 會檢查回應裡有沒有 cookie 或密碼。
- **不用 `NEXT_PUBLIC_*` 放設定**（建置時就固定了），執行期設定走 `shared/runtime/`。
- **`apps/web/proxy.ts` 留在原位**：放錯位置 Next 照樣建置成功，路由保護卻整層消失。
- **畫面上的權限判斷只是體驗**，真正的檢查在後端的 `require(...)`。
- **後台的寫入要守住三條防提權的規則**（不授予自己沒有的權限、不管理權限比自己高的帳號、不改自己的角色與狀態），
  新增會改到帳號或角色的功能時比照 `modules/users/service.py`。
- **AUDIT、log 與任務的 payload 只放 id 與固定的代碼**，不放帳號、暱稱或使用者輸入的內容。
  `make e2e check` 會掃描 E2E 用過的值，E2E 沒走到的路徑掃不到。
- **背景任務必須能重跑**；任務名稱不要改。
- **上傳的檔案存在 `/app/uploads/<模組>/`**：存到別的路徑，重建容器就消失，也備份不到。
  `make e2e check` 會列出 E2E 期間寫在 volume 以外的檔案。
- **schema、路由函式與 enum 的 docstring 會進公開的 API 契約**，不放內部說明。
- **主機的 reverse proxy 在 repo 之外**：它要覆寫 `X-Real-IP` 與 `X-Forwarded-Proto`，少了不會報錯
  （[說明](docs/foundation/operations.md#主機的-reverse-proxy)）。
- **compose 的旗標不要自己組**，一律經過 `tools/compose.py`。
- **`docs/foundation/` 與基礎建設歸 foundation**（[檔案歸誰](docs/foundation/workflow.md#檔案歸誰)）：在子專案裡改了，
  下次同步就會衝突。專案自己的說明與決定寫在 `docs/project/`，基礎建設的修正先回到 foundation。

## 授權界線

做錯了 CI 或審查抓得到、revert 就能復原的，自己處理；決定使用者的意圖、不可逆、會讓保證變弱或讓 agent 的權限變大的，
由使用者決定。hook 只擋常見的那幾種寫法，沒被擋下不代表可以做。

**自己處理，不用問**：

- 需求明確時整理驗收條件、寫測試與實作、開 Draft PR
- 新增測試檔、在既有的測試檔加新的案例與輔助程式
- 讀 CI 的錯誤、修正、push 工作分支，直到全綠
- commit、更新 PR 描述、自審、轉 Ready for review
- 被 hook 或檢查擋下後改做法、縮小改動（不是換個寫法做同一件事）

**先停下來說明要做什麼、為什麼，等使用者同意**；沒列到但你判斷同樣危險的，也照辦：

- 意圖還沒定：產品行為、權限的取捨、資料怎麼處理，或需求有兩種以上合理的解讀
- 超出驗收條件的範圍
- 讓保證變弱：改或刪既有測試的程式碼、放寬斷言、跳過測試、加抑制註解、降低門檻
- 改防線檔案（hook、agent 設定、CI、檢查的設定與入口）
- 不可逆或影響 repo 以外的動作：部署、發布、刪資料或分支、動主機、改別的 repo、送出外部服務
- 升級相依：先在乾淨的環境實際安裝並跑過檢查，確認整組相容；有不相容的要告知並提出替代方案
- 還有開著的 PR 時插隊開分支（`feature-workflow`〈插隊〉）

**不做**：

- 合併 PR（由使用者做）、直接 push `main`
- 繞過檢查（`--no-verify`、改 `core.hooksPath`），或為了通過而停用檢查
- 自己寫放行紀錄，或換個寫法完成被 hook 擋下的同一個動作

**同意的效力跟著任務的範圍，不跟著修了幾輪**。範圍以 Draft PR「驗證」段的驗收條件為準：同一個任務、目的與範圍內，
同意過的不再問，CI 修幾輪、審查退回幾次都一樣；也不因為修了很多輪就順手做範圍外的事。
目標環境、受影響的資料或風險變了（例如從補測試變成要放寬斷言）才重新問。

被 hook 擋下時照它給的理由做。**要改既有的測試與防線檔案**：在對話訊息裡一次列出所有檔案與原因，最後才問一句是否全部同意，
同意後執行一次 `approve.py`（[流程](docs/foundation/testing.md#改程式不改測試)）。

## 寫程式

- **要進 `main` 的改動照 `feature-workflow` skill**（Feature Branch → Draft PR → Incremental Commits → Code Review →
  Squash Merge）：驗收條件寫進 Draft PR 的「驗證」段，每條有對應的驗證方式，改了行為的就是測試名稱
  （[說明](docs/foundation/testing.md#驗收條件與驗證方式)）。新行為與 bug 修正先寫測試再實作。
- **一次只有一個進行中的 PR**；要插隊照 `feature-workflow`〈插隊〉先問使用者。
- **每個 commit 最後加 `Co-authored-by: <產品> <模型與版本> <email>`**。
- **測試變紅時預設它是對的**，改實作讓它變綠。
- **測試放該 app 的 `tests/`，與原始碼同構**。`actions.ts` 與 `ui/*.tsx` 不寫執行期測試，
  畫面的分支抽進 `capabilities.ts` 再測。不要為了覆蓋率數字補測試。
- **優先讓程式碼自行表達意圖**；必要的註解簡短說明原因或限制（[說明](docs/foundation/development.md#註解與文件)）。
- **參考既有寫法時，先確認情境適用**：避免直接沿用別處的特殊處理。
- **單次的糾正留在當下的任務**；要成為長期規則時，寫得成檢查就寫成檢查，寫不成的記進文件並寫明理由。
- 程式碼裡的註解用半形標點，字串與 Markdown 用全形。
- **CSS 只用設計變數**，不寫死色值或尺寸。
- 一個任務交給一個 agent；不要兩個 agent 同時改同一個分支。

## 改完之後

| 改了什麼 | 要做 |
|---|---|
| 任何程式碼 | 本機依影響範圍跑需要的 `make check <項目>`；push 後照 `watch-pr` 等 CI，合併只認 CI |
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
