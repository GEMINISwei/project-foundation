/** 路由的組裝點。這份檔案會被 proxy.ts 載入, 所以只能用 Edge runtime 跑得動的東西。 */

import type { ModuleManifest, RouteArea } from "@/shared/module"
import { canAccessRoute } from "@/shared/access/permissions"
import { AUTH_MODULE } from "@/modules/auth/manifest"
import { ROLES_MODULE } from "@/modules/roles/manifest"
import { SETTINGS_MODULE } from "@/modules/settings/manifest"
import { USERS_MODULE } from "@/modules/users/manifest"

/**
 * 前端唯一的模組啟用清單。底下的執行期陣列與型別聯集**全部**從這一份推導 —— 新增模組只要在
 * 這裡加一行, `PROTECTED_ROUTES`、`AREA_ROUTES`、`NavIconKey` 就會自動跟上。陣列順序
 * 同時決定側欄導覽的顯示順序。
 *
 * `as const satisfies` 兩個都要: `satisfies` 檢查每個 manifest 的形狀, `as const` 保住字面值
 * 型別 —— 少了它, 路徑與圖示代號會退化成 `string`, 編譯期保護就沒了。
 */
const ENABLED_MODULES = [
  AUTH_MODULE,
  USERS_MODULE,
  ROLES_MODULE,
  SETTINGS_MODULE,
] as const satisfies readonly ModuleManifest[]

/** 啟用清單裡所有路由的聯集。沒有路由的模組貢獻 `never`, 會自動從聯集消失。 */
type EnabledRoute = (typeof ENABLED_MODULES)[number]["protectedRoutes"][number]

// 型別標成 `EnabledRoute` 而不是 `ProtectedRoute`: 後者會把 navIcon 放寬成 `string`,
// `NAV_ICONS` 的窮盡檢查就會失效。
export const PROTECTED_ROUTES: readonly EnabledRoute[] = ENABLED_MODULES.flatMap(
  (module) => [...module.protectedRoutes],
)

export type NavIconKey = EnabledRoute["navIcon"]

/** 各區的路由, 順序即導覽順序。 */
export const AREA_ROUTES: Record<RouteArea, readonly EnabledRoute[]> = {
  admin: PROTECTED_ROUTES.filter((route) => route.group === "admin"),
  user: PROTECTED_ROUTES.filter((route) => route.group === "user"),
}

/**
 * 某一區裡這個使用者進得去的路由。
 *
 * 管理區的進入檢查、外殼的導覽列與切換區域的連結都用它, 所以「看得到連結」與「實際進得去」
 * 必然一致。這一層只是體驗, 真正的授權在後端。
 */
export function accessibleRoutes(area: RouteArea, permissions: readonly string[]) {
  return AREA_ROUTES[area].filter((route) => canAccessRoute(permissions, route))
}

/** 導覽列要列出的路由: 進得去, 而且沒有標成 `showInNav: false` (入口在別處的頁面)。 */
export function navRoutes(area: RouteArea, permissions: readonly string[]) {
  return accessibleRoutes(area, permissions).filter((route) => route.showInNav)
}

export function isProtectedPathname(pathname: string): boolean {
  return PROTECTED_ROUTES.some(
    (route) => pathname === route.path || pathname.startsWith(`${route.path}/`),
  )
}
