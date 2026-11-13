# 架構

規則與介面，以及為什麼這樣定。操作步驟見 [`new-module.md`](new-module.md)、[`permissions.md`](permissions.md)、
[`migrations.md`](migrations.md)、[`jobs.md`](jobs.md)。

## 為什麼這樣設計

- **一個功能是一個模組**：資料、規則、API 與畫面放在一起。新增時照抄一個模組，移除時整包拿掉，不必改 `shared/`。
- **邊界由工具檢查，不靠約定**：最省事的寫法常常跨出邊界，每次單看都合理，累積起來模組就糾纏在一起。
- **跨模組只走 public entry、只以 ID 參照**：模組內部怎麼改，只要 public 不變就不影響別人。
- **漏了不會報錯的事，要變成會報錯**：權限、語系、端點寫錯是編譯錯誤；設定缺漏在啟動時失敗。
- **出問題要查得到**：每個請求有追蹤 id、每個錯誤有固定代碼、安全事件進資料表。

## 分層

前後端用同一套三層，依賴只能往右：

```text
app（組裝層） → modules（一個功能一個模組） → shared（平台能力）
```

| | 後端 `apps/api/` | 前端 `apps/web/` |
|---|---|---|
| 組裝層 | `app/`：啟用哪些模組、權限 enum、進入點 | `config/`：啟用清單、外殼；`app/`：Next 的路由檔，只做接線 |
| 模組 | `modules/<name>/` | `modules/<name>/` |
| 平台 | `shared/` | `shared/` |
| 測試 | `tests/`，與原始碼同構 | `tests/`，與原始碼同構 |

前後端都有的模組一律同名。只有前端有的 `auth`、`settings` 是純畫面，呼叫 `users` 的端點。

### 依賴規則

1. `shared` 不可引用 `modules` 或組裝層。
2. 模組不可引用組裝層。唯一例外是後端的 `app.permissions`（見〈[權限](#權限)〉）。
3. 跨模組只能引用對方的 public entry：後端 `public.py`，前端 `public.server.ts`／`public.client.ts`。
4. 組裝層也一樣，只能引用模組的 public entry 或 manifest。
5. 前端的 manifest 會在 edge runtime 載入，連間接依賴都不能碰 React、Next 或 `.server` 檔。
6. 前端模組內部用相對路徑，`@/` 只用來跨層；UI 元件只從 `@/shared/ui` 匯入。
7. 後端不開 `services/`、`repositories/`、`utils/` 這類水平分層的頂層目錄；public 不轉出資料表。

| 規則 | 後端由誰檢查 | 前端由誰檢查 |
|---|---|---|
| 1–4 | import-linter（`pyproject.toml`） | dependency-cruiser（`.dependency-cruiser.cjs`） |
| 5、6 | — | dependency-cruiser、ESLint |
| 7 | `tests/test_architecture.py` | `tests/architecture.test.ts` |

**少量重複不等於 shared。** 還沒有第二個使用者、或含有某個業務規則時，先留在模組。

## 後端模組

```text
modules/<name>/
├── manifest.py      # 必備。對平台宣告: 路由、資料表、權限、事件、任務、初始資料
├── public.py        # 其他模組唯一可以引用的檔案: 函式與它們的回傳型別
├── router.py        # 路由: 宣告需要的權限, 把請求交給 service
├── schema.py        # 請求與回應的形狀 (pydantic)
├── service.py       # 業務規則; 回傳 schema, 不回傳資料表物件
├── repository.py    # 資料庫查詢; 回傳資料表物件, 不做業務判斷
├── model.py         # 資料表: 只有欄位與關聯
├── errors.py        # 這個模組的錯誤 (代碼與雙語訊息)
└── permissions.py   # 有引入權限時: 標籤、分類與相依關係
```

- service 長大就依**授權模型**拆檔，不開 `services/`。例：`users` 的 `service.py`（管理者對別人）、
  `account.py`（使用者對自己）、`superuser.py`（只給指令用）。
- 啟用清單只有一處：`app/registry.py`。撞名（模組、路由前綴、資料表、任務）在啟動時就被拒絕。
- schema、路由函式與 enum 的 docstring 會進 OpenAPI 與前端型別檔，只寫給呼叫端看的說明。

### 資料層

- 資料表繼承 `Entity`（`shared/db/base.py`）：UUIDv7 主鍵、建立與更新時間。時間一律帶時區。
- 一次請求（或一個任務、一次指令）是一個工作單元：一個 session、一個交易，結束時整批 commit 或 rollback。
  repository 用 `db()` 取得目前的 session，不必逐層傳。
- 列表用游標分頁：`paginate(Model, params, where=[...])`，回應是 `Page[T]`。
- 唯一約束衝突由 service 轉成自己的錯誤；外鍵違反由平台統一轉成 409。

### 模組之間的資料關聯

**先決定怎麼切**：經常一起查、一起改、有共同規則要同時成立的放同一個模組；只需要「指到的東西存在」的分開。
分開之後對方的 public 多到像把內部原封不動轉出去，就是邊界畫錯了。

- 跨模組照樣建外鍵，用字串宣告（`ForeignKey("roles.id")`），不 import 對方的資料表。
  `ondelete` 由持有外鍵的一方決定，業務資料預設 `RESTRICT`。
- 要對方的資料就呼叫對方 `public.py` 的函式。提供的一方要有**批次**版本，使用的一方一次補完整頁，
  查詢次數不隨筆數增加（例：`users` 的列表用 `get_roles(ids)`，有測試鎖住查詢次數）。
- 跨模組的函式不收 session，自然與呼叫端在同一個交易裡。
- **反方向的需求**（被參照的一方要知道誰在參照它）：先交給資料庫的 `RESTRICT`；需要業務上的連動或否決時用
  模組事件（`shared/events.py`）：被參照的模組在 public 定義事件並 `publish()`，參照它的模組在 manifest 的
  `event_handlers` 訂閱。處理函式在發布者的交易裡執行，丟出錯誤就否決整個操作。
- 寄信、呼叫外部服務這類「提交之後才該發生」的副作用，排成背景任務（見 [`jobs.md`](jobs.md)）。

## 前端模組

```text
modules/<name>/
├── manifest.ts          # 必備。這個模組的頁面: 區域、路徑、權限、導覽
├── i18n.ts              # 必備。這個模組的中英字串
├── public.server.ts     # 給其他模組與路由檔用的伺服器端入口
├── public.client.ts     # 給其他模組用的畫面規則與字典
├── page.server.tsx      # 取資料、檢查權限, 交給 ui/<Name>View
├── actions.ts           # "use server" 的寫入動作
├── capabilities.ts      # 畫面的分支規則 (純函式, 要寫測試)
├── types.ts、validation.ts …
└── ui/                  # 元件、只服務畫面的 hook、CSS module
```

- 模組根放資料與規則，`ui/` 放畫面；不開 `components/`、`hooks/`、`utils/`。
- `app/` 的 `page.tsx` 只做轉接，而且要**逐一轉接 Next 特有的 export**（`generateMetadata` 等），
  Next 只讀路由檔自己的 export，漏了不會報錯（`tests/app/route-adapters.test.ts` 會比對）：

  ```tsx
  import { XPage, generateXMetadata, type XPageProps } from "@/modules/x/public.server"
  export const generateMetadata = generateXMetadata
  export default function Page(props: XPageProps) { return <XPage {...props} /> }
  ```

- 瀏覽器不直接呼叫後端。讀取在 Server Component，寫入包成具名的 Server Action：

  ```ts
  const result = await call(api.GET("/api/roles/{role_id}", { params: { path: { role_id } } }))
  ```

  `api` 的路徑、參數與回應型別都來自契約；`call` 把結果整理成 `ApiResult`，登入失效時導向登入頁。
- 執行期設定不用 `NEXT_PUBLIC_*`（建置時就固定了），走 `shared/runtime/`。
- 使用者看得到的字串都要中英兩份，放在擁有它那一層的 `i18n.ts`；少翻一個 key 是編譯錯誤。
- CSS 只用設計變數（`shared/ui/styles/tokens.css` 定義，專案在 `app/theme.css` 覆寫）。

### 前台與後台

頁面放哪一區看**操作的對象**：

| 區域 | 放什麼 | 規則 |
|---|---|---|
| 後台 `admin` | 管理系統本身或別人的資料（使用者、角色） | 路徑以 `/admin/` 開頭，一定要宣告權限 |
| 前台 `user` | 使用者處理自己的業務、自己的帳號 | 路徑不可以用 `/admin/` |

同一個模組可以兩區都有頁面（前台「我的訂單」、後台「全部訂單」）。

每個頁面在模組的 manifest **宣告一次**，導覽、路由保護與「進入後台」的入口都從它推導（`config/routes.ts`）：

```ts
const USERS_ROUTE = {
  path: "/admin/users",
  label: { zh: "使用者", en: "Users" },
  group: "admin",                                   // 區域, 頁面檔放在對應的目錄
  section: { zh: "帳號與權限", en: "Accounts & access" },  // 導覽分組, 文字相同的排在一起
  requires: ["users:read"],                         // 有其中任何一個就能進入
  navIcon: "users",                                 // 圖示在 config/shell/nav-icons.ts 登記
  showInNav: true,
} as const satisfies ProtectedRoute
```

- 導覽項目只在使用者有 `requires` 的權限時顯示；至少進得去一個後台頁面才看得到「進入後台」。
- 頁面在最前面呼叫 `requirePermission("users:read")`，沒有就導回首頁。
- 頁面內的按鈕（新增、編輯）用 `hasPermission()` 的結果決定顯示，規則寫在 `capabilities.ts`。
- 以上都只是體驗。**真正的授權在後端的每個端點**。
- 區域與路徑、頁面檔的位置是否一致，由 `tests/config/routes.test.ts` 檢查。

## 權限

- 權限值集中定義在 `app/permissions.py` 的 enum，命名一律 `資源:動作`。集中是刻意的：enum 進 OpenAPI 後是字串聯集，
  前端打錯權限名稱會編譯失敗。
- 每個權限的標籤、分類與相依關係由引入它的模組在 `permissions.py` 宣告。enum 有值而沒有模組宣告，啟動時就失敗。
- **相依關係**：「有 A 就一定要有 B」（`users:write` 需要 `users:read`）。儲存角色時後端自動補上，
  畫面上勾選時也會連動。所以「看得到」完全由 Read 權限決定。
- **超級管理者**是 `*`，只存在於系統角色、只能用指令建立（`make db superuser`）、後台不能指派也不能管理。
- 路由用 `Depends(require(Permission.USERS_READ))` 宣告；不帶參數是「只要登入」。
- 後台分權之後，有三條規則防止提權（都在後端強制）：
  1. 不能授予自己沒有的權限、不能指派含有自己沒有的權限的角色。
  2. 不能管理（修改、停用、重設密碼）權限比自己高的帳號，也不能修改、停用或重新啟用權限比自己高的角色。
  3. 不能停用自己、不能改自己的角色。

## 每個請求經過什麼

`shared/platform.py` 的 middleware 固定做這些事，模組不必自己處理：

1. 依 `Accept-Language` 決定語系。
2. 沿用上游的 `X-Request-ID`（nginx 產生、web 轉送），沒有就產生一個；之後每一行 log 都帶著它。
3. 開一個資料庫交易。回應是 4xx／5xx 就 rollback，否則 commit。
4. **commit 之後才送出回應**：用戶端收到成功時資料一定已經寫入。
5. 把這次請求的 AUDIT 紀錄寫進資料表（另開交易，請求失敗也留得住；`committed` 記錄這次的寫入有沒有成立）。
6. 記一筆請求紀錄：方法、路徑、狀態碼、耗時、使用者。超過 1 秒記成 warning。

HTTP 以外的入口（任務、指令）經過同一個 `unit_of_work()`，拿到相同的交易、事件與 AUDIT。

### 錯誤

每個錯誤有固定的代碼，訊息跟著語系走，回應一律是同一個形狀：

```json
{ "code": "roles.name_exists", "message": "角色名稱已存在", "request_id": "7ef748b5…", "fields": [] }
```

```python
ROLE_NAME_EXISTS = ErrorSpec(409, "roles.name_exists", LangText(zh="角色名稱已存在", en="…"))
raise ROLE_NAME_EXISTS()
```

不用裸的 `HTTPException`（ruff 會擋）。畫面上的錯誤訊息會附上 request id，使用者回報時可以直接查
（見 [`operations.md`](operations.md#出問題怎麼查)）。

## 前後端契約

```text
後端的路由與 schema ──make gen-types──▶ contracts/openapi.json ──▶ apps/web/shared/api/schema.d.ts
```

兩份產出都進版控，對外介面的變更在 review 的 diff 裡看得到。CI 的 `contract` 會重產一次比對，不一致就擋。
業務型別在用到它的模組的 `types.ts` 以 `Schema<"RoleInfo">` 命名，移除模組時型別跟著消失。

## 移除一個模組

| 位置 | 動作 |
|---|---|
| `apps/api/modules/<name>/`、`apps/api/tests/modules/<name>/` | 整包刪除 |
| `apps/api/app/registry.py`、`app/permissions.py` | 移除 manifest 與它的權限值 |
| `apps/web/modules/<name>/`、`apps/web/tests/modules/<name>/`、`app/` 底下它的路由目錄 | 整包刪除 |
| `apps/web/config/routes.ts`、`config/shell/nav-icons.ts` | 移除 manifest 與圖示 |

收尾先 `make gen-types` 再 `make check types`：前端還在用的已刪除端點或權限會變成編譯錯誤。
資料表要另外新增一支 migration 刪除。角色裡留著的那些權限值會在下一次 migrate 時清掉
（`modules/roles/seed.py`），模組之後加回來要重新勾選。`users` 與 `roles` 是核心模組，不移除。
