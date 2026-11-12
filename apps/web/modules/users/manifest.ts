import type { ModuleManifest, ProtectedRoute } from "@/shared/module"

/** 管理區是真正的路徑段, 所以模組內的連結都要帶 `/admin` 前綴。 */
export const USERS_PATH = "/admin/users"

// 導覽分組以文字相同為準: 與 roles 模組宣告同一組文字, 兩個頁面就排在同一組。
const ACCESS_SECTION = { zh: "帳號與權限", en: "Accounts & access" } as const

const USERS_ROUTE = {
  path: USERS_PATH, label: { zh: "使用者", en: "Users" }, group: "admin", section: ACCESS_SECTION, requires: ["users:read"], navIcon: "users", showInNav: true,
} as const satisfies ProtectedRoute

export const USERS_MODULE = {
  name: "users",
  protectedRoutes: [USERS_ROUTE],
} as const satisfies ModuleManifest
