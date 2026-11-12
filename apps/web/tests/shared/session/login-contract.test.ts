import { describe, expect, it } from "vitest"

import { LOGIN_PATH, LOGIN_REDIRECT_REASONS, loginUrl } from "@/shared/session/login-contract"

describe("loginUrl", () => {
  it("沒有原因時導向不帶參數的登入頁，有原因時帶上 reason", () => {
    expect(loginUrl()).toBe(LOGIN_PATH)
    expect(loginUrl(LOGIN_REDIRECT_REASONS.sessionExpired)).toBe(
      `${LOGIN_PATH}?reason=session-expired`,
    )
  })
})
