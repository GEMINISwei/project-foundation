# 測試

## 為什麼這樣設計

- **測行為，不測實作**：測試名稱是一句「在什麼情況下會怎樣」。內部怎麼改，行為不變測試就不該變紅。
- **新行為與 bug 修正先寫測試，再寫實作**：測試是驗收條件的可執行版本，先寫才不會寫成配合實作的樣子。
  重構不改行為，靠既有的測試保持綠燈；設定與型別整理靠對應的檢查。
- **需要資料庫的就連真的資料庫**：交易、約束、鎖的行為用假的替身測不出來。
- **設定檔與腳本交給現成的工具檢查**（actionlint、shellcheck、`compose config`），不另外寫測試去讀它們。
- **合併與部署只認 CI 的結果**：本機依影響範圍跑需要的檢查，完整的一輪交給 CI。

## 測試放哪裡

| 位置 | 測什麼 | 怎麼跑 |
|---|---|---|
| `apps/api/tests/` | 後端。與原始碼同構（`tests/modules/users/` 對 `modules/users/`） | `make check api-test`、`make check integration` |
| `apps/web/tests/` | 前端的規則與共用元件。與原始碼同構 | `make check web-test` |
| `e2e/tests/` | 整套系統從瀏覽器走一遍 | `make e2e test <檔案>`、`make e2e check` |
| `.agents/hooks/tests/`、`.agents/skills/<skill>/tests/`、`tools/tests/` | agent 的 hook、skill 的腳本、`make` 指令。skill 的測試目錄旁要有自己的 `pytest.ini` | 併在 `make check api-test` |

放在這些目錄以外的測試不會執行，也不會報錯。

### 後端

- 不需要資料庫的直接跑；需要的在檔案開頭標 `pytestmark = pytest.mark.integration`。
- integration 測試用 `client` fixture 從 HTTP 打進去，建資料用 `tests/helpers.py`（`admin_headers`、
  `create_role`、`user_with`）。每個測試從清空的資料庫開始。
- 寫測試時只跑那幾個：`make check integration tests/modules/users/test_users.py`（會起一個拋棄式的 PostgreSQL）。
- 警告一律視為錯誤：相依套件標成過時的用法要在升級之前處理掉。

### 前端

- `actions.ts` 與 `ui/*.tsx` 不寫執行期測試。畫面有分支時把規則抽進 `capabilities.ts` 再測。
- `.server` 檔在測試裡用 `vi.mock` 換掉 `next/headers`、`next/navigation`（例：`tests/shared/api/client.server.test.ts`）。

### E2E

只放**整套跑起來才看得到**的行為：導向、cookie 屬性、Server Action、權限、登入狀態撤銷。畫面的分支用前端測試。

```bash
make e2e up                           # 起一套常駐的 E2E 開發環境 (獨立的容器、資料與 port)
make e2e test tests/auth/login.spec.ts
make e2e grep "登出"
make e2e down
make e2e check                        # 用正式環境的映像檔跑全部, 再實際備份還原一次; CI 跑的就是這個
```

- 每次 `test` 前會把資料重設成只有一個超管；測試要的資料自己建（`tests/support.ts`）。
- 不開 retries：偶發失敗要修等待條件，不能靠重跑。
- 只在手機版才有意義的測試標 `@mobile-only`，兩種裝置都要跑的標 `@mobile`。
- CI 裡每個測試結束時都截圖，報告每次上傳，Job summary 有連結：截圖是審查時的證據，不只用來除錯。
  本機不截圖。
- spec 一律從 `support` 匯入 `test`（`import { test } from "../support"`），執行期契約的檢查才會套用；
  直接從 `@playwright/test` 匯入 `test` 時 `make e2e` 會拒絕執行。

### 執行期契約

系統跑起來之後，對**全部**的路由、請求與容器驗同一件事。新功能不必另外寫測試就會被涵蓋，
補上〈漏了不會報錯的地方〉那幾條原本只靠記得的規則。

| 契約 | 在哪裡驗 | 怎麼驗 |
|---|---|---|
| 每條路由都宣告權限，而且真的擋得住 | 後端整合測試 `tests/app/test_route_permissions.py` | 列出 `/api` 底下所有路由，不登入要 401、沒權限要 403、剛好有權限不能被擋；沒宣告也沒標 `public()` 的列出來 |
| 瀏覽器不直接呼叫後端 | E2E 的共用 fixture（`tests/support.ts`） | 每個測試記錄瀏覽器發出的請求，打到 `/api/` 或別的網站就失敗 |
| Server Action 不把憑證送進瀏覽器 | E2E 的共用 fixture | Server Action 的回應裡出現 cookie 的值或測試密碼就失敗 |
| 使用者輸入不進 log、AUDIT 與任務 | `make e2e check` 跑完測試後 | 測試期間新增到資料庫的文字欄位與測試密碼，拿去掃描各服務的 log、`audit_logs`、`jobs` |
| 資料只寫在會保存的位置 | `make e2e check` 跑完測試後 | `docker diff` 列出 volume 與 bind mount 以外的寫入 |

- 沒通過時，後兩項寫進 `e2e` job 的 Job summary（哪個欄位出現在哪裡、哪個容器寫了哪個路徑），其餘由測試失敗。
- 掃描只找得到 E2E 實際用過的值；E2E 沒走到的功能，外洩也看不到。
- 容器寫入的允許清單在 `tools/commands/e2e.py` 的 `ALLOWED_WRITES`，只放暫存與快取（`/tmp`、`/run`、nginx 的快取、
  nginx 啟動時從 template 產生的設定、Next 的 `.next/cache`）。要加進清單之前，先確認那個路徑重建後消失也沒關係。

## 覆蓋率門檻

防退步的地板，不是目標：後端在 `pyproject.toml` 的 `fail_under`，前端在 `vitest.config.ts` 的 `thresholds`。
不要為了數字補測試；門檻擋下來時先看缺的是哪個行為。

## 驗收條件與驗證方式

動手之前列出驗收條件，開 Draft PR 時寫進「驗證」段。**每一條都有驗證方式**，依工作性質選：

| 工作 | 驗證方式 |
|---|---|
| 新行為、bug 修正 | 測試名稱（bug 寫能重現的測試） |
| 重構 | 涵蓋那段程式的既有測試，列出名稱，保持綠燈 |
| 設定、相依、型別整理 | 對應的 CI job 或指令（`lint`、`types`、`build`…） |
| 只改 Markdown | 可以檢查的結果（「README 的快速開始照著做得起來」） |
| 以上都做不到 | 人工驗收：寫明誰、在哪裡、看什麼 |

```text
- 管理者不能停用自己的帳號 → test_nobody_can_disable_themselves_or_change_their_own_roles
- 只有查看權限的帳號看不到新增按鈕 →「只有查看權限的帳號進得了後台，但看不到新增與編輯」
```

- 改了行為的條件寫不出測試名稱，就是要先問清楚的地方；不要退回人工驗收。
- AI agent 在需求明確時自己整理驗收條件；牽涉產品行為、權限的取捨、資料怎麼處理，或需求有兩種以上合理的解讀時，
  **先給使用者確認才開始寫測試**。
- 驗收條件就是這個任務的範圍：修幾輪都以它為準，對不上任何一條的改動另外問或另開 PR。
- 後端用 `test_<在什麼情況下會怎樣>`，前端與 E2E 用中文句子。

## 改程式不改測試

實作開始之後，測試變紅**預設它是對的**，改實作讓它變綠。測試被改成配合實作時，所有檢查都是綠的，沒有任何東西會提醒。

補測試不用問：新增測試檔、在既有的測試檔加新的案例與輔助程式，既有的驗證都還在。
只改測試檔的註解、docstring 或空行也不用問，它們不影響任何斷言。

會讓既有的驗證變弱的才要先問（改斷言、刪測試、跳過測試、改掉既有的輔助檔與測試資料）：

1. 在對話訊息裡**一次列出**這次要改的所有測試檔。清單不放進詢問視窗：項目一多會顯示不完，使用者看不到就無法判斷。
2. 每個檔案簡短說明：驗證的條件、沒過的原因、打算怎麼改，以及為什麼是測試而不是實作要改。
   寫完才問一句是否全部同意。
3. 使用者同意後執行一次 `python3 .agents/hooks/approve.py test <檔案…>`（會跳一次確認）再改，
   並在 PR 的「驗證」段寫出改了哪些測試檔與原因。防線檔案的流程相同，類別換成 `protected`。

同意過的檔案在這個任務裡不再問，修幾輪都一樣。

AI agent 這一側由 hook 把關，放行之後在這個分支上改這些檔案不再詢問（[測試鎖](hooks-and-skills.md#測試鎖)）。
用 shell 指令改檔不會被攔，一樣要先問。

「實作開始了」從 git 推導：分支相對 `main` 的差異裡有 `apps/`、`e2e/`、`tools/`、`.agents/hooks/`、
`.github/scripts/` 底下不是測試也不是 Markdown 的檔案。
