import { describe, expect, it } from "vitest"
import { AREA_ROUTES } from "@/config/routes"
import { getAccountMenuEntries } from "@/config/shell/account-menu"

const labels = (entries: ReturnType<typeof getAccountMenuEntries>) => entries.map((e) => e.label)

describe("getAccountMenuEntries", () => {
  it("超級管理者在使用者區看得到管理後台的入口，連到第一個管理頁", () => {
    const entries = getAccountMenuEntries("user", ["*"])

    expect(labels(entries)).toEqual(["goAdminArea", "accountSettings", "logout"])
    expect(entries[0]).toMatchObject({ href: AREA_ROUTES.admin[0].path })
  })

  it("在管理區一律能回使用者區", () => {
    const entries = getAccountMenuEntries("admin", ["*"])

    expect(labels(entries)).toEqual(["goUserArea", "accountSettings", "logout"])
    expect(entries[0]).toMatchObject({ href: "/" })
  })

  it("一般帳號沒有切換區域的項目，只有設定與登出", () => {
    expect(labels(getAccountMenuEntries("user", []))).toEqual(["accountSettings", "logout"])
  })
})
