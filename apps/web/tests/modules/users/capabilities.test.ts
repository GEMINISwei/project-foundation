import { describe, expect, it } from "vitest"
import {
  formatRoleNames,
  getUserActions,
  isAssignableRole,
  isSuperAdminUser,
  roleIdsForUpdate,
} from "@/modules/users/capabilities"
import type { RoleInfo, UserInfo } from "@/modules/users/types"

type RoleRef = UserInfo["roles"][number]

const STAFF: RoleRef = { id: "r-staff", name: "員工", code: null, is_disabled: false }
const OLD: RoleRef = { id: "r-old", name: "舊職務", code: null, is_disabled: true }
const SUPER: RoleRef = { id: "r-super", name: "Super Admin", code: "super_admin", is_disabled: false }

function user(roles: RoleRef[], id = "u-1"): UserInfo {
  return { id, username: "u", nickname: "U", is_disabled: false, roles }
}

describe("isSuperAdminUser", () => {
  it("看的是系統角色的代碼，不是角色名稱", () => {
    expect(isSuperAdminUser(user([SUPER]))).toBe(true)
    expect(isSuperAdminUser(user([{ ...STAFF, name: "Super Admin" }]))).toBe(false)
    expect(isSuperAdminUser(user([]))).toBe(false)
  })
})

describe("formatRoleNames", () => {
  const t = ((key: string, values?: Record<string, unknown>) => {
    if (key === "roleDisabledSuffix") return `${values?.name}（停用中）`
    if (key === "roleSeparator") return "、"
    return "未指派"
  }) as never
  const roleT = ((key: string) => (key === "roleSuperAdmin" ? "超級管理者" : key)) as never

  it("多個角色以分隔字串串起來，停用的帶後綴", () => {
    expect(formatRoleNames(user([STAFF, OLD]), t, roleT)).toBe("員工、舊職務（停用中）")
  })

  it("系統角色顯示字典裡的名稱", () => {
    expect(formatRoleNames(user([SUPER]), t, roleT)).toBe("超級管理者")
  })

  it("一個角色都沒有時是未指派", () => {
    expect(formatRoleNames(user([]), t, roleT)).toBe("未指派")
  })
})

describe("getUserActions", () => {
  it("有寫入權限時可以對別人做所有操作", () => {
    expect(getUserActions(user([STAFF]), "someone-else", true, true)).toEqual({
      canEdit: true,
      canResetPassword: true,
      canAssignRole: true,
      canToggleStatus: true,
    })
  })

  it("只有查看權限時什麼都不能做", () => {
    expect(Object.values(getUserActions(user([STAFF]), "someone-else", false, true))).toEqual([
      false, false, false, false,
    ])
  })

  it("對自己可以改資料，但不能停用自己或改自己的角色", () => {
    expect(getUserActions(user([STAFF], "me"), "me", true, true)).toMatchObject({
      canEdit: true,
      canAssignRole: false,
      canToggleStatus: false,
    })
  })

  it("超級管理者的帳號後台完全不能動", () => {
    expect(Object.values(getUserActions(user([SUPER]), "someone-else", true, true))).toEqual([
      false, false, false, false,
    ])
  })

  it("沒有角色清單時不提供指派角色", () => {
    expect(getUserActions(user([STAFF]), "someone-else", true, false).canAssignRole).toBe(false)
  })
})

describe("roleIdsForUpdate", () => {
  it("不能指派角色時原樣送回", () => {
    expect(roleIdsForUpdate(false, "r-new", ["r-old"])).toEqual(["r-old"])
  })

  it("選擇沒變時原樣送回，原本的多個角色不會被單選欄位清掉", () => {
    expect(roleIdsForUpdate(true, "r-a", ["r-a", "r-b"])).toEqual(["r-a", "r-b"])
    expect(roleIdsForUpdate(true, "", [])).toEqual([])
  })

  it("改選之後只留新的那一個；選未指派就清空", () => {
    expect(roleIdsForUpdate(true, "r-new", ["r-a", "r-b"])).toEqual(["r-new"])
    expect(roleIdsForUpdate(true, "", ["r-a"])).toEqual([])
  })
})

describe("isAssignableRole", () => {
  const role = (overrides: Partial<RoleInfo>): RoleInfo => ({
    id: "r", name: "r", code: null, permissions: [], is_disabled: false, ...overrides,
  })

  it("只有啟用中的一般角色可以指派", () => {
    expect(isAssignableRole(role({}))).toBe(true)
    expect(isAssignableRole(role({ is_disabled: true }))).toBe(false)
    expect(isAssignableRole(role({ code: "super_admin" }))).toBe(false)
  })
})
