import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"
import { isProtectedPathname } from "@/config/routes"
import { LOCALE_COOKIE, isLocale, resolveLocale } from "@/shared/i18n/locale"
import { ACCESS_TOKEN_COOKIE, LOGIN_PATH } from "@/shared/session/login-contract"

// 受保護路由的清單在 config/routes.ts, 導覽列也讀同一份 —— 新增頁面只要改那個檔案, 這層保護
// 就會自動跟上。這裡是「快速擋下」的第一層; 即使漏掉, (protected)/layout.tsx 的伺服器端檢查
// 仍會攔截, 只是慢一步。
//
// 這裡也是語系 cookie 的**唯一**初始化點: 伺服器端唯一看得到 `Accept-Language` 的地方就是這
// 一層 (Server Component 讀得到 headers, 但那時已經沒有回應可以寫 cookie 了)。

function getLoginUrl(request: NextRequest) {
  const url = request.nextUrl.clone()
  url.pathname = LOGIN_PATH
  url.search = ""

  return url
}

/**
 * 首次進站時, 依 `Accept-Language` 決定語系並寫進 cookie。
 *
 * 只在 cookie 不存在時做: 已經有 cookie 還去看 header 的話, 使用者在設定頁選的語言會被瀏覽器
 * 語言蓋掉, 而且只在某些路徑上發生, 症狀非常難重現。
 *
 * redirect 的回應也要寫: 沒登入的人第一站是 `/login`, 那一頁拿不到 cookie 就會用預設語系先
 * 渲染一次, 畫面會閃一下。
 */
function ensureLocaleCookie(request: NextRequest, response: NextResponse) {
  if (isLocale(request.cookies.get(LOCALE_COOKIE)?.value)) return response

  response.cookies.set(LOCALE_COOKIE, resolveLocale(request.headers.get("accept-language")), {
    // 與 `shared/i18n/actions.ts` 的 setLocale 一致。這裡沒有 maxAge: 這只是一個
    // 猜測值, 讓它隨瀏覽器關閉而消失, 下次開啟時重新依當下的瀏覽器語言判斷。
    // 使用者真的在設定頁選過之後, 那一份才是帶 maxAge 的長期偏好。
    httpOnly: false,
    sameSite: "lax",
    path: "/",
  })

  return response
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const hasToken = Boolean(request.cookies.get(ACCESS_TOKEN_COOKIE)?.value)
  const isServerAction = request.headers.has("next-action")

  if (pathname === "/") {
    if (!hasToken) {
      return ensureLocaleCookie(request, NextResponse.redirect(getLoginUrl(request)))
    }

    return ensureLocaleCookie(request, NextResponse.next())
  }

  if (isProtectedPathname(pathname) && !hasToken && !isServerAction) {
    return ensureLocaleCookie(request, NextResponse.redirect(getLoginUrl(request)))
  }

  return ensureLocaleCookie(request, NextResponse.next())
}

// `healthz` 也排除: 那是 Docker healthcheck 每 10 秒打一次的探活端點 (app/healthz/route.ts),
// 它不需要保護, 也不該每次都被寫一次語系 cookie。
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public/|healthz).*)"],
}
