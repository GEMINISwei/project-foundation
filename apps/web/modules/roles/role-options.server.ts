import "server-only"
import { api, call } from "@/shared/api/client.server"
import type { RoleInfo } from "./types"

/** 不分頁的完整角色清單, 給其他模組的下拉選單用。失敗時回傳空清單。 */
export async function getRoleOptions(): Promise<RoleInfo[]> {
  const result = await call(api.GET("/api/roles/options"))
  return result.ok ? result.data.items : []
}
