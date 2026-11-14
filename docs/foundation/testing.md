# 測試

## 為什麼這樣設計

- **測行為，不測實作**：測試名稱是一句「在什麼情況下會怎樣」。內部怎麼改，行為不變測試就不該變紅。
- **先寫測試，再寫實作**：測試是驗收條件的可執行版本，先寫才不會寫成配合實作的樣子。
- **需要資料庫的就連真的資料庫**：交易、約束、鎖的行為用假的替身測不出來。
- **設定檔與腳本交給現成的工具檢查**（actionlint、shellcheck、`compose config`），不另外寫測試去讀它們。
- **完整的檢查只在 CI 跑**：合併與部署只認 CI 的結果；本機只跑正在寫的那一項。

## 測試放哪裡

| 位置 | 測什麼 | 怎麼跑 |
|---|---|---|
| `apps/api/tests/` | 後端。與原始碼同構（`tests/modules/users/` 對 `modules/users/`） | `make check api-test`、`make check integration` |
| `apps/web/tests/` | 前端的規則與共用元件。與原始碼同構 | `make check web-test` |
| `e2e/tests/` | 整套系統從瀏覽器走一遍 | `make e2e test <檔案>`、`make e2e check` |
| `.agents/hooks/tests/`、`tools/tests/` | agent 的 hook、`make` 指令 | 併在 `make check api-test` |

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
make e2e check                        # 用正式環境的映像檔跑全部, CI 跑的就是這個
```

- 每次 `test` 前會把資料重設成只有一個超管；測試要的資料自己建（`tests/support.ts`）。
- 不開 retries：偶發失敗要修等待條件，不能靠重跑。
- 只在手機版才有意義的測試標 `@mobile-only`，兩種裝置都要跑的標 `@mobile`。

## 覆蓋率門檻

防退步的地板，不是目標：後端在 `pyproject.toml` 的 `fail_under`，前端在 `vitest.config.ts` 的 `thresholds`。
不要為了數字補測試；門檻擋下來時先看缺的是哪個行為。

## 驗收條件與測試名稱

動手之前列出驗收條件，**每一條對應一個測試名稱**，開 Draft PR 時寫進「驗證」段：

```text
- 管理者不能停用自己的帳號 → test_nobody_can_disable_themselves_or_change_their_own_roles
- 只有查看權限的帳號看不到新增按鈕 →「只有查看權限的帳號進得了後台，但看不到新增與編輯」
```

- 寫不出測試名稱的那一條，就是要先問清楚的地方。
- AI agent 寫的驗收條件，**先給使用者確認才開始寫測試**：把談定的方向轉成測試名稱時最容易漏情境或擴大範圍。
- 後端用 `test_<在什麼情況下會怎樣>`，前端與 E2E 用中文句子。
- 只改 Markdown 的 PR 不寫測試，驗收條件寫成可以檢查的結果（「README 的快速開始照著做得起來」）。

## 改程式不改測試

實作開始之後，測試變紅**預設它是對的**，改實作讓它變綠。測試被改成配合實作時，所有檢查都是綠的，沒有任何東西會提醒。

要動測試檔（改斷言、刪測試、補新測試、輔助檔與測試資料）之前：

1. 在對話訊息裡**一次列出**這次要改的所有測試檔。
2. 每個檔案簡短說明：驗證的條件、沒過的原因、打算怎麼改，以及為什麼是測試而不是實作要改。
   寫完才問一句是否全部同意。
3. 使用者同意後才改，並在 PR 的「驗證」段寫出改了哪些測試檔與原因。

AI agent 這一側由 hook 把關：改檔工具動到測試檔會被擋下，照上面說明後執行一次
`python3 .agents/hooks/approve.py test <檔案…>`（會跳一次確認），之後在這個分支上改這些檔案不再詢問
（[說明](hooks-and-skills.md#測試鎖)）。用 shell 指令改檔不會被攔，一樣要先問。

「實作開始了」從 git 推導：分支相對 `main` 的差異裡有 `apps/`、`e2e/`、`tools/`、`.agents/hooks/`、
`.github/scripts/` 底下不是測試也不是 Markdown 的檔案。
