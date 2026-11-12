/**
 * 路由保護第一層 (`proxy.ts`) 的分支測試。
 *
 * 這一層決定「還沒登入的人打受保護網址時, 要不要在進到 render 之前就導去 `/login`」。
 * 它有第二層防護 (`app/(protected)/layout.tsx` 的伺服器端檢查), 所以這裡出錯不會直接
 * 變成資料外洩 —— 但兩種失敗方向都很難自己浮現:
 *
 * - 該擋沒擋 → 使用者仍會被第二層擋下, 只是多跑一次 render, 沒人會注意到保護失效了。
 * - 不該擋卻擋 → Server Action 被導去登入頁, 表單送出後畫面莫名跳走。
 *
 * 所以用測試把每條分支釘住。
 *
 * 這一層還有第二個責任: **語系 cookie 的初始化**。伺服器端唯一看得到 `Accept-Language`
 * 的地方就是這裡 (Server Component 讀得到 headers, 但那時已經沒有回應可以寫 cookie 了),
 * 而它的失敗方向同樣安靜 —— 寫錯只是整站退回預設語系, 覆寫則是把使用者在設定頁選的
 * 語言默默換掉。
 */

import { describe, expect, it } from "vitest"
import { NextRequest } from "next/server"
import { PROTECTED_ROUTES } from "@/config/routes"
import { proxy } from "@/proxy"

// 從啟用清單取一條受保護路由, 不寫死 `/admin/users`: 模組增減時這批測試不該跟著壞。
const PROTECTED = PROTECTED_ROUTES[0].path

const TOKEN_COOKIE = "access_token=fake-token"

function request(
  path: string,
  options?: { token?: boolean; serverAction?: boolean; acceptLanguage?: string; locale?: string },
) {
  const headers = new Headers()
  const cookies = [
    options?.token ? TOKEN_COOKIE : null,
    options?.locale ? `locale=${options.locale}` : null,
  ].filter((entry): entry is string => entry !== null)

  if (cookies.length > 0) headers.set("cookie", cookies.join("; "))
  if (options?.acceptLanguage) headers.set("accept-language", options.acceptLanguage)
  // Next.js 送 Server Action 時會帶這個 header; proxy 靠它區分「導覽」與「表單送出」。
  if (options?.serverAction) headers.set("next-action", "abc123")

  return new NextRequest(`http://localhost${path}`, { headers })
}

/** 回應實際寫出去的 locale cookie 值; 沒寫就是 undefined。 */
function localeCookieOf(response: Response): string | undefined {
  return (response as unknown as { cookies: { get(name: string): { value: string } | undefined } })
    .cookies.get("locale")?.value
}

/** NextResponse.next(): 放行, 不帶 Location。 */
function expectPassThrough(response: Response) {
  expect(response.status).toBe(200)
  expect(response.headers.get("location")).toBeNull()
}

function expectRedirectToLogin(response: Response) {
  expect(response.status).toBe(307)
  expect(response.headers.get("location")).toBe("http://localhost/login")
}

describe("proxy", () => {
  describe("首頁", () => {
    it("未登入導向 /login", async () => {
      expectRedirectToLogin(await proxy(request("/")))
    })

    it("已登入放行", async () => {
      expectPassThrough(await proxy(request("/", { token: true })))
    })
  })

  describe("受保護路由", () => {
    it("未登入導向 /login", async () => {
      expectRedirectToLogin(await proxy(request(PROTECTED)))
    })

    it("已登入放行", async () => {
      expectPassThrough(await proxy(request(PROTECTED, { token: true })))
    })

    it("導向時清掉 query string", async () => {
      // 原網址的 query 可能帶游標、篩選條件甚至 ws ticket, 不該原封不動接到登入頁上。
      const response = await proxy(request(`${PROTECTED}?cursor=abc&name=secret`))
      expect(response.headers.get("location")).toBe("http://localhost/login")
    })

    it("Server Action 即使沒有 token 也放行", async () => {
      // 登入本身就是一個打在公開頁上的 Server Action; 把它導去 /login 會讓登入永遠送不出去。
      // 真正的授權在後端, 未帶 token 的 action 會拿到 401。
      expectPassThrough(await proxy(request(PROTECTED, { serverAction: true })))
    })
  })

  describe("公開路由", () => {
    it("/login 未登入也放行", async () => {
      expectPassThrough(await proxy(request("/login")))
    })

  })

  describe("語系 cookie", () => {
    it("首次進站依 Accept-Language 決定", async () => {
      const response = await proxy(request("/login", { acceptLanguage: "en-US,en;q=0.9" }))

      expect(localeCookieOf(response)).toBe("en")
    })

    it("沒有 Accept-Language 時用預設語系", async () => {
      expect(localeCookieOf(await proxy(request("/login")))).toBe("zh")
    })

    it("認不出的 Accept-Language 用預設語系", async () => {
      expect(localeCookieOf(await proxy(request("/login", { acceptLanguage: "ja-JP" })))).toBe("zh")
    })

    it("已經有 cookie 就不覆寫 —— 即使瀏覽器語言不同", async () => {
      // 這條是整組裡最重要的: 覆寫會讓使用者在設定頁選的語言被瀏覽器語言默默蓋掉,
      // 而且只在有經過 proxy 的路徑上發生, 症狀非常難重現。
      const response = await proxy(
        request("/login", { locale: "zh", acceptLanguage: "en-US,en;q=0.9" }),
      )

      expect(localeCookieOf(response)).toBeUndefined()
    })

    it("認不出的 cookie 值視同沒有，重新判斷", async () => {
      const response = await proxy(request("/login", { locale: "ja", acceptLanguage: "en" }))

      expect(localeCookieOf(response)).toBe("en")
    })

    it("導向登入頁的回應也要帶上 cookie", async () => {
      // 未登入者的第一站就是這個 redirect。這裡不寫的話, 登入頁會先用預設語系渲染一次
      // 再被下一個請求修正, 畫面會閃一下。
      const response = await proxy(request(PROTECTED, { acceptLanguage: "en" }))

      expectRedirectToLogin(response)
      expect(localeCookieOf(response)).toBe("en")
    })

    it("已登入的首頁與受保護路由同樣會初始化", async () => {
      expect(localeCookieOf(await proxy(request("/", { token: true, acceptLanguage: "en" })))).toBe("en")
      expect(localeCookieOf(await proxy(request(PROTECTED, { token: true, acceptLanguage: "en" })))).toBe("en")
    })
  })
})
