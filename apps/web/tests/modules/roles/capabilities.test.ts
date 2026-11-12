import { describe, expect, it } from "vitest"
import {
  canManageRole,
  groupPermissionOptions,
  togglePermission,
} from "@/modules/roles/capabilities"
import type { PermissionOption, RoleInfo } from "@/modules/roles/types"

describe("groupPermissionOptions", () => {
  const option = (value: string, category: string) =>
    ({ value, label: value, category }) as PermissionOption

  it("依 category 分組，組與組內都保留後端的順序", () => {
    const groups = groupPermissionOptions([
      option("users:create", "使用者"),
      option("roles:read", "角色"),
      option("users:read", "使用者"),
    ])

    expect(groups.map((group) => group.category)).toEqual(["使用者", "角色"])
    expect(groups[0].options.map((item) => item.value)).toEqual(["users:create", "users:read"])
  })

  it("每一個選項都會出現在某一組裡（不會有被吃掉的權限）", () => {
    const options = [option("a:read", "A"), option("b:read", "B"), option("c:read", "C")]

    expect(groupPermissionOptions(options).flatMap((group) => group.options)).toHaveLength(3)
  })
})

describe("canManageRole", () => {
  const role = (code: string | null) =>
    ({ id: "r", name: "r", code, permissions: [], is_disabled: false }) as RoleInfo

  it("一般角色可以編輯", () => {
    expect(canManageRole(role(null))).toBe(true)
  })

  it("系統角色不能編輯（由模板擁有）", () => {
    expect(canManageRole(role("super_admin"))).toBe(false)
  })
})

describe("togglePermission", () => {
  const options = [
    { value: "users:read", label: "", category: "", requires: [] },
    { value: "users:write", label: "", category: "", requires: ["users:read", "roles:read"] },
    { value: "roles:read", label: "", category: "", requires: [] },
    { value: "roles:write", label: "", category: "", requires: ["roles:read"] },
  ] as PermissionOption[]

  it("勾選時一併勾上它需要的權限", () => {
    expect(togglePermission([], "users:write", options)).toEqual([
      "users:read", "users:write", "roles:read",
    ])
  })

  it("取消時一併取消需要它的權限", () => {
    const all = ["users:read", "users:write", "roles:read", "roles:write"] as const

    expect(togglePermission(all, "roles:read", options)).toEqual(["users:read"])
  })

  it("取消沒有人需要的權限不影響其他的", () => {
    expect(togglePermission(["users:read", "users:write", "roles:read"], "users:write", options))
      .toEqual(["users:read", "roles:read"])
  })

  it("結果依後端給的順序排列", () => {
    expect(togglePermission(["roles:write", "roles:read"], "users:read", options)).toEqual([
      "users:read", "roles:read", "roles:write",
    ])
  })
})
