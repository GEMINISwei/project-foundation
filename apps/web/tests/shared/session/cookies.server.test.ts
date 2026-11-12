/**
 * cookie 寫入與刪除的原語 (`shared/session/cookies.server.ts`)。
 *
 * 選項要原封不動交給 Next: 少傳一個 `httpOnly` 或 `sameSite`, cookie 照樣寫得進去, 只是少了一道保護。
 */

import { beforeEach, describe, expect, it, vi } from "vitest"

const set = vi.fn()
const remove = vi.fn()

vi.mock("next/headers", () => ({
  cookies: async () => ({ set, delete: remove }),
}))

const { createCookies, deleteCookies } = await import("@/shared/session/cookies.server")

beforeEach(() => vi.clearAllMocks())

describe("cookies.server", () => {
  it("寫入 cookie 時帶上指定的選項", async () => {
    const options = {
      httpOnly: true, secure: true, sameSite: "lax" as const, path: "/", maxAge: 3600,
    }

    await createCookies("access_token", "jwt", options)

    expect(set).toHaveBeenCalledWith("access_token", "jwt", options)
  })

  it("刪除時移除指定的 cookie", async () => {
    await deleteCookies("access_token")

    expect(remove).toHaveBeenCalledWith("access_token")
    expect(set).not.toHaveBeenCalled()
  })
})
