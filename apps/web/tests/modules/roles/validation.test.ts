import { describe, expect, it } from "vitest"

import { validateRoleName } from "@/modules/roles/validation"

describe("validateRoleName", () => {
  it("角色名稱空白的錯誤標在名稱欄位", () => {
    expect(validateRoleName("  ", "zh")).toBeTruthy()
    expect(validateRoleName("業務", "zh")).toBeUndefined()
  })
})
