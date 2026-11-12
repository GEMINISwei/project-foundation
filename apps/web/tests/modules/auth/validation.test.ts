import { describe, expect, it } from "vitest"
import { getLoginRedirectReason } from "@/modules/auth/validation"

describe("getLoginRedirectReason", () => {
  it("認得約定裡的導向原因", () => {
    expect(getLoginRedirectReason("session-expired")).toBe("session-expired")
  })

  it("不認得的值、陣列與缺值一律當成沒有原因", () => {
    // query 參數是使用者可以亂改的, 不認得的值不能變成畫面上的提示。
    expect(getLoginRedirectReason("bogus")).toBeUndefined()
    expect(getLoginRedirectReason(["session-expired"])).toBeUndefined()
    expect(getLoginRedirectReason(undefined)).toBeUndefined()
  })
})
