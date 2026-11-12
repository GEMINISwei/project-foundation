/**
 * session cookie 的寫入與清除 (`shared/session/access-token.server.ts`)。
 *
 * 這裡的設定錯了都不會有症狀: cookie 照樣寫得進去, 只是少了一道保護或壽命不對。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const createCookies = vi.fn()
const deleteCookies = vi.fn()
let forwardedProto: string | null = "https"

vi.mock("next/headers", () => ({
  headers: async () => ({ get: () => forwardedProto }),
}))
vi.mock("@/shared/session/cookies.server", () => ({ createCookies, deleteCookies }))

const { clearAccessTokenCookie, setAccessTokenCookie } = await import(
  "@/shared/session/access-token.server"
)

function writtenOptions() {
  const [name, value, options] = createCookies.mock.calls[0]
  return { name, value, options }
}

describe("setAccessTokenCookie", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    forwardedProto = "https"
  })
  afterEach(() => vi.unstubAllEnvs())

  it("寫成 httpOnly、sameSite=lax，壽命跟著 EXPIRE_HOURS", async () => {
    vi.stubEnv("EXPIRE_HOURS", "8")

    await setAccessTokenCookie("jwt")

    expect(writtenOptions()).toEqual({
      name: "access_token",
      value: "jwt",
      options: { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 8 * 3600 },
    })
  })

  it.each(["", "abc", "0", "-3"])("EXPIRE_HOURS 是 %j 時退回 1 小時，而不是變成 session cookie", async (value) => {
    // `maxAge: NaN` 會讓 cookie 在關掉瀏覽器時消失, 而且沒有任何警告。
    vi.stubEnv("EXPIRE_HOURS", value)

    await setAccessTokenCookie("jwt")

    expect(writtenOptions().options.maxAge).toBe(3600)
  })

  it("走 http 進來時不標 secure（否則瀏覽器根本不存這個 cookie）", async () => {
    forwardedProto = "http"

    await setAccessTokenCookie("jwt")

    expect(writtenOptions().options.secure).toBe(false)
  })
})


describe("clearAccessTokenCookie", () => {
  beforeEach(() => vi.clearAllMocks())

  it("清除 access token 時刪掉 access token 的 cookie", async () => {
    await clearAccessTokenCookie()

    expect(deleteCookies).toHaveBeenCalledWith("access_token")
    expect(createCookies).not.toHaveBeenCalled()
  })
})
