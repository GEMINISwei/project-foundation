"use server"

/**
 * 切換語系。**具名、窄介面**的 Server Action: 只收 `Locale` 聯集, 只寫一個 cookie
 * (理由見 `shared/session/cookies.server.ts` 檔頭)。
 *
 * 放在 `shared/i18n/` 而不是組裝層: 設定頁 (`modules/settings/`) 要呼叫它, 而 module 不可以
 * 反向引用 `config/`。
 */

import { revalidatePath } from "next/cache"
import { headers } from "next/headers"
import { resolveCookieSecure } from "@/shared/session/cookie-options"
import { createCookies } from "@/shared/session/cookies.server"
import { type Locale, DEFAULT_LOCALE, isLocale, LOCALE_COOKIE } from "./locale"

// 一年。語系是使用者的長期偏好, 不該跟著 session 一起過期 —— 登出後回到登入頁時,
// 那一頁也要維持使用者選的語言。
const LOCALE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

export async function setLocale(locale: Locale) {
  // Server Action 的參數來自網路, 型別在執行期不成立。認不出來就退回預設值,
  // 不要把任意字串寫進 cookie (它會被原樣送進後端的 Accept-Language)。
  const resolved = isLocale(locale) ? locale : DEFAULT_LOCALE
  const headerStore = await headers()

  await createCookies(LOCALE_COOKIE, resolved, {
    // 刻意**不是** httpOnly: 語系不是機密, 而讓瀏覽器端讀得到, 之後要做「未經 Server
    // Action 的即時切換」才有路可走。
    httpOnly: false,
    secure: resolveCookieSecure(headerStore.get("x-forwarded-proto")),
    sameSite: "lax",
    path: "/",
    maxAge: LOCALE_MAX_AGE_SECONDS,
  })

  // 整棵樹都要重畫: Server Component 的字串、`<html lang>`、後端依 Accept-Language 回的訊息
  // 都跟著語系走, 只 revalidate 當前頁面會留下一半舊語言。
  revalidatePath("/", "layout")
}
