# 權限

規則見 [`architecture.md`](architecture.md#權限)。這裡是新增一個權限的步驟。

## 步驟

1. **加進 enum**（`apps/api/app/permissions.py`），命名 `資源:動作`：

   ```python
   PRODUCTS_READ = "products:read"
   PRODUCTS_WRITE = "products:write"
   ```

2. **在模組的 `permissions.py` 宣告**標籤、分類與相依關係，並放進 manifest 的 `permissions`：

   ```python
   _CATEGORY = LangText(zh="商品", en="Products")

   PERMISSIONS = (
       PermissionSpec(Permission.PRODUCTS_READ, LangText(zh="查看", en="View"), _CATEGORY),
       PermissionSpec(
           Permission.PRODUCTS_WRITE,
           LangText(zh="新增與修改", en="Create and edit"),
           _CATEGORY,
           requires=frozenset({Permission.PRODUCTS_READ}),
       ),
   )
   ```

3. **路由宣告需要的權限**：`Depends(require(Permission.PRODUCTS_READ))`。
4. `make gen-types`。前端的 `Permission` 型別會多出這兩個值，manifest 的 `requires` 與 `hasPermission()` 才用得到。
5. **前端**：頁面的 manifest 寫 `requires: ["products:read"]`，頁面開頭 `requirePermission("products:read")`，
   寫入的按鈕用 `hasPermission(permissions, "products:write")` 決定顯示。

角色編輯畫面不必改：選項、標籤與分組都來自後端。

## 怎麼切權限

- **每個資源至少分 Read 與 Write**。看不看得到完全由 Read 決定，所以其他權限都要 `requires` 它。
- 需要更細時再加（`products:delete`、`orders:refund`），不要一開始就把每個按鈕都做成權限。
- 一個權限用到別的模組的資料時，把那個模組的 Read 列進 `requires`（`users:write` 要列出角色，所以需要 `roles:read`）。
- **不做資料範圍**（只能看自己的、部門的）。需要時在那個功能的 service 裡依登入者過濾，並寫測試；
  有第二個功能需要同一種範圍時再抽成共用的做法。
