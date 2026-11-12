import "server-only"
import { cache } from "react"
import { redirect } from "next/navigation"
import { hasPermission } from "@/shared/access/permissions"
import { api, call } from "@/shared/api/client.server"
import type { Permission } from "@/shared/api/types"

/**
 * 目前登入者。用 React 的 `cache` 包住: 同一次頁面請求裡 layout、外殼與頁面都會問, 只打一次後端。
 * 沒登入或登入失效時回傳 null (後端回 401 的情況 `call` 已經導向登入頁)。
 */
export const getCurrentUser = cache(async () => {
  const result = await call(api.GET("/api/users/me"))
  return result.ok ? result.data : null
})

/**
 * 頁面需要某個權限時在最前面呼叫: 沒有就導回首頁。
 * 這只是體驗 (不讓人停在一個每個請求都被拒絕的頁面), 真正的授權在後端的每個端點。
 */
export async function requirePermission(permission: Permission) {
  const user = await getCurrentUser()
  if (!hasPermission(user?.permissions ?? [], permission)) redirect("/")
  return user
}
