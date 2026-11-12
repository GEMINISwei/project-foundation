# 新增模組

以 `products` 為例。最快的做法是**照抄 `roles`**（前後端都是），再改成自己的內容。

## 後端

1. 建 `apps/api/modules/products/`，檔案的分工見 [`architecture.md`](architecture.md#後端模組)：

   ```python
   # manifest.py
   MODULE = ModuleManifest(
       name="products",
       routers=(router,),
       models=(Product,),
       permissions=PERMISSIONS,
   )
   ```

2. 在 `app/registry.py` 的 `ENABLED_MODULES` 加上它。
3. 有權限的話照 [`permissions.md`](permissions.md) 加進 enum 並宣告。
4. `make db migration "add products"`，讀過產出（[`migrations.md`](migrations.md)）。
5. 測試放 `apps/api/tests/modules/products/`。
6. `make gen-types`。

寫的時候注意：

- **model 只放欄位**，查詢放 `repository.py`，規則放 `service.py`。
- **錯誤**在 `errors.py` 宣告，代碼用 `products.<原因>`：

  ```python
  PRODUCT_NOT_FOUND = ErrorSpec(404, "products.not_found", LangText(zh="商品不存在", en="Product not found"))
  ```

- **列表**用 `paginate()` 與 `Page[T]`；給下拉選單的完整清單另開一條路由回 `ItemList[T]`，不要讓同一條路由回兩種形狀。
- **安全相關的操作**呼叫 `audit("product_deleted", product_id=...)`。
- **回應裡的時間**直接用 `datetime`：資料庫與程式裡都是帶時區的 UTC，序列化出去帶著時區。
- **上傳**的請求上限固定 16MB，每個上傳功能自己訂更小的上限並回傳明確的錯誤。

## 前端

1. 建 `apps/web/modules/products/`，檔案的分工見 [`architecture.md`](architecture.md#前端模組)。
2. 在 `manifest.ts` 宣告頁面（[前台或後台](architecture.md#前台與後台)），把 manifest 加進 `config/routes.ts` 的
   `ENABLED_MODULES`，圖示加進 `config/shell/nav-icons.ts`（漏了會編譯失敗）。
3. 在 `app/(protected)/admin/products/page.tsx`（或 `(user)/`）建路由檔，只做轉接。
4. 型別在 `types.ts` 用 `Schema<"ProductInfo">` 命名。
5. 字串放 `i18n.ts`，中英兩份。
6. 測試放 `apps/web/tests/modules/products/`：`capabilities.ts` 與 `validation.ts` 要測。
7. 改到登入、導向、權限的流程時，在 `e2e/tests/` 加一支。

## 檢查清單

- [ ] 後端 `registry.py`、前端 `routes.ts` 都加了
- [ ] 權限加進 enum，而且有模組宣告它
- [ ] migration 讀過
- [ ] `make gen-types` 的兩份產出一起 commit
- [ ] `CHANGELOG.md` 的 `[Unreleased]` 留了一筆
