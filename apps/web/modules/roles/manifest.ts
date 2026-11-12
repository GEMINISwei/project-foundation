import type { ModuleManifest, ProtectedRoute } from "@/shared/module"

/** 管理區是真正的路徑段, 所以模組內的連結都要帶 `/admin` 前綴。 */
export const ROLES_PATH = "/admin/roles"

// 導覽分組以文字相同為準: 與 users 模組宣告同一組文字, 兩個頁面就排在同一組。
const ACCESS_SECTION = { zh: "帳號與權限", en: "Accounts & access" } as const

const ROLES_ROUTE = {
  path: ROLES_PATH, label: { zh: "角色", en: "Roles" }, group: "admin", section: ACCESS_SECTION, requires: ["roles:read"], navIcon: "roles", showInNav: true,
} as const satisfies ProtectedRoute

export const ROLES_MODULE = {
  name: "roles",
  protectedRoutes: [ROLES_ROUTE],
} as const satisfies ModuleManifest
