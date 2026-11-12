import { describe, expect, it } from "vitest"
import { canAccessRoute, hasAllPermission, hasPermission } from "@/shared/access/permissions"

describe("hasPermission", () => {
  it("要有那個權限，或是超級管理者", () => {
    expect(hasPermission(["users:read"], "users:read")).toBe(true)
    expect(hasPermission(["users:read"], "users:write")).toBe(false)
    expect(hasPermission(["*"], "users:write")).toBe(true)
    expect(hasPermission([], "users:read")).toBe(false)
  })

  it("只有萬用權限算超級管理者", () => {
    expect(hasAllPermission(["*"])).toBe(true)
    expect(hasAllPermission(["users:read", "users:write", "roles:read", "roles:write"])).toBe(false)
  })
})

describe("canAccessRoute", () => {
  it("沒有宣告權限的路由登入就能進", () => {
    expect(canAccessRoute([], { requires: [] })).toBe(true)
  })

  it("宣告了權限的路由，擁有其中任何一個就能進", () => {
    const route = { requires: ["users:read", "roles:read"] as const }

    expect(canAccessRoute(["roles:read"], route)).toBe(true)
    expect(canAccessRoute(["roles:write"], route)).toBe(false)
    expect(canAccessRoute(["*"], route)).toBe(true)
    expect(canAccessRoute([], route)).toBe(false)
  })
})
