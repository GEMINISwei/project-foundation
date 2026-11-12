/**
 * 前端模組的 manifest: 一個模組對外殼宣告它有哪些頁面。
 *
 * 每個頁面只在這裡宣告一次, 導覽、路由保護與「進入後台」的入口都從它推導 (config/routes.ts)。
 * manifest 會被 proxy.ts 在 edge runtime 載入, 所以不能引用 React、Next 或 .server 檔。
 *
 * 頁面放哪一區看操作的對象:
 * - `admin` (後台): 管理系統本身或別人的資料。路徑以 `/admin/` 開頭, 一定要宣告權限。
 * - `user`  (前台): 使用者處理自己的業務與自己的帳號。路徑不可以用 `/admin/`。
 * 同一個模組可以兩區都有頁面 (前台「我的訂單」、後台「全部訂單」)。規則由 tests/config/routes.test.ts 檢查。
 */

import type { Permission } from "@/shared/api/types"
import type { LocaleText } from "@/shared/i18n/locale"

export type RouteArea = "admin" | "user"

export type ProtectedRoute = {
  path: string
  /** 導覽列顯示的名稱。不走字典: manifest 所在的那一層沒有查字典需要的 React context。 */
  label: LocaleText
  /** 所屬區域, 頁面檔放在對應的目錄: `app/(protected)/admin/` 或 `app/(protected)/(user)/`。 */
  group: RouteArea
  /** 導覽的分組標題; 同一區裡文字相同的排在同一組。`null` 是不分組。 */
  section: LocaleText | null
  /** 擁有其中任何一個權限就能進入 (通常是這個頁面的查看權限); 空陣列是登入即可。 */
  requires: readonly Permission[]
  /** 圖示代號, 對應的圖示在 config/shell/nav-icons.ts 登記 (漏了會編譯失敗)。 */
  navIcon: string
  /** `false` 的頁面一樣受保護, 只是入口在別處 (例如設定頁在頭像選單)。 */
  showInNav: boolean
}

export type ModuleManifest = {
  name: string
  /** 沒有頁面的模組寫 `[]`, 不做成選填: 「沒有頁面」與「忘了寫」才分得出來。 */
  protectedRoutes: readonly ProtectedRoute[]
}
