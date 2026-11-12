import type { Permission } from "@/shared/api/types"

// 走 `has()` 而不是直接 `permissions.includes("...")`: 參數標成 Permission 之後,
// 權限字串打錯或後端刪掉某個權限時, 這裡會**編譯失敗**而不是靜默回傳 false。
function includesPermission(permissions: readonly string[], permission: Permission) {
  return permissions.includes(permission)
}

export function hasAllPermission(permissions: readonly string[]) {
  return includesPermission(permissions, "*")
}

/** 這個人有沒有某個權限 (超級管理者一律有)。畫面上的按鈕與導覽都用它判斷。 */
export function hasPermission(permissions: readonly string[], permission: Permission) {
  return hasAllPermission(permissions) || includesPermission(permissions, permission)
}

function hasAnyPermission(permissions: readonly string[], required: readonly Permission[]) {
  return required.some((permission) => hasPermission(permissions, permission))
}

/**
 * 判斷使用者能不能進入某條路由。
 *
 * 導覽列 (AppShell) 與存取控制 (admin/layout.tsx) 都呼叫這一個函式,
 * 所以不可能出現「側欄看得到但點進去被踢出來」這種不一致。
 *
 * 這只是 UX 層的把關 —— 真正的授權在後端 (`shared/auth/identity.py` 的 `require`), 直接打 API 一樣會被擋。
 */
export function canAccessRoute(
  permissions: readonly string[],
  route: { requires: readonly Permission[] },
) {
  if (route.requires.length === 0) return true
  if (hasAllPermission(permissions)) return true

  return hasAnyPermission(permissions, route.requires)
}
