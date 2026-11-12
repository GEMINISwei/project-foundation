import { beforeEach, describe, expect, it, vi } from "vitest"

let localeCookie: string | undefined

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (key: string) => (key === "locale" && localeCookie ? { value: localeCookie } : undefined),
  }),
}))

const { getLocale } = await import("@/shared/i18n/locale.server")

describe("getLocale", () => {
  beforeEach(() => {
    localeCookie = undefined
  })

  it("用 cookie 裡的語系", async () => {
    localeCookie = "en"

    await expect(getLocale()).resolves.toBe("en")
  })

  it.each([undefined, "fr", ""])("cookie 是 %j 時退回預設語系", async (value) => {
    // 被竄改或過時的值不能一路傳到後端的 Accept-Language。
    localeCookie = value

    await expect(getLocale()).resolves.toBe("zh")
  })
})

