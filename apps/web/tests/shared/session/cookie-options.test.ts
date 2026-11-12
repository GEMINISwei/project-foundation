import { describe, expect, it } from "vitest"
import { resolveCookieSecure } from "@/shared/session/cookie-options"

/**
 * 這個判斷錯的後果**兩個方向都是無聲的**:
 *
 * - 多給了 Secure: HTTP 部署下瀏覽器直接丟棄 access_token, 登入成功卻被 proxy.ts 導回
 *   /login, 沒有任何錯誤訊息。
 * - 少給了 Secure: HTTPS 部署下 token 會被明文連線帶出去, 一樣沒有任何徵兆。
 *
 * 所以這裡把 header 的各種實際長相都釘住。
 */
describe("resolveCookieSecure", () => {
  it("https 要加 Secure", () => {
    expect(resolveCookieSecure("https")).toBe(true)
  })

  it("http 不加 Secure（這正是 MODE=production 的 make start 走 nginx plain HTTP 的情況）", () => {
    expect(resolveCookieSecure("http")).toBe(false)
  })

  it("多層 proxy 串起來時看第一段——那才是面對用戶端的協定", () => {
    expect(resolveCookieSecure("https, http")).toBe(true)
    expect(resolveCookieSecure("http, https")).toBe(false)
  })

  it("大小寫與空白不影響判斷", () => {
    expect(resolveCookieSecure(" HTTPS ")).toBe(true)
    expect(resolveCookieSecure("Https,http")).toBe(true)
  })

  it("讀不到 header 時退回不加 Secure，而不是讓登入靜默失敗", () => {
    expect(resolveCookieSecure(null)).toBe(false)
    expect(resolveCookieSecure(undefined)).toBe(false)
    expect(resolveCookieSecure("")).toBe(false)
  })

  it("不認得的值一律不算 https", () => {
    expect(resolveCookieSecure("wss")).toBe(false)
    expect(resolveCookieSecure("httpsx")).toBe(false)
  })
})
