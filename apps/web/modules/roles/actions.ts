"use server"

import { api, call } from "@/shared/api/client.server"
import { ROLES_PATH } from "./manifest"
import type { RoleUpdate } from "./types"

const refresh = { revalidate: ROLES_PATH }

// 建立時不帶權限, 權限在編輯頁另外設定: 對外的介面刻意比後端窄。
export async function createRole(data: { name: string }) {
  return call(api.POST("/api/roles", { body: { name: data.name, permissions: [] } }), refresh)
}

export async function updateRole(id: string, data: RoleUpdate) {
  return call(
    api.PUT("/api/roles/{role_id}", { params: { path: { role_id: id } }, body: data }),
    refresh,
  )
}
