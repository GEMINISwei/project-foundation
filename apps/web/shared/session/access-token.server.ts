// 寫入與清除 session cookie 的**唯一**出口。登入 (`modules/auth`) 與改密碼 (`modules/settings`)
// 都走這裡 —— 兩邊各寫一份的話, `httpOnly`/`secure`/`sameSite` 就有兩個會各自飄的來源,
// 而飄掉的那一份**不會有任何症狀**: cookie 照樣寫得進去, 只是少了一道保護。
// (同 `cookies.server.ts` 對「create/get/delete 成套提供」的說法。)
//
// **不要在這個檔案加上 "use server"**: 這是原語, 不是端點。成為 Server Action 之後,
// client 就能把任意字串寫進 `access_token` (session fixation)。
import "server-only"

import { headers } from "next/headers"

import { resolveCookieSecure } from "./cookie-options"
import { createCookies, deleteCookies } from "./cookies.server"
import { ACCESS_TOKEN_COOKIE } from "./login-contract"

// EXPIRE_HOURS 沒設或格式錯誤時, `Number()` 會得到 NaN, 而 `maxAge: NaN` 會讓 cookie 變成
// session cookie (關掉瀏覽器就登出) 而且沒有任何警告。這裡明確給一個保守的預設值。
const DEFAULT_EXPIRE_HOURS = 1

function getCookieMaxAgeSeconds() {
  const hours = Number(process.env.EXPIRE_HOURS)

  return 60 * 60 * (Number.isFinite(hours) && hours > 0 ? hours : DEFAULT_EXPIRE_HOURS)
}

/**
 * 以後端剛簽發的 token 覆寫 session cookie。
 *
 * cookie 的 `maxAge` 與 token 的 `exp` 各自由兩邊的 `EXPIRE_HOURS` 算出來, 所以那個值
 * **前後端必須是同一個** (compose 把同一份 `.env` 餵給兩個容器)。不一致的話症狀是
 * 「cookie 還在但請求 401」, 或反過來「cookie 提早消失」——兩者都看不出是設定問題。
 */
export async function setAccessTokenCookie(token: string) {
  const headerStore = await headers()

  await createCookies(ACCESS_TOKEN_COOKIE, token, {
    httpOnly: true,
    // 依這次請求實際走的協定決定, 而不是依 NODE_ENV —— 理由見 resolveCookieSecure。
    secure: resolveCookieSecure(headerStore.get("x-forwarded-proto")),
    // sameSite: "lax" 是目前的 CSRF 防線: 跨站發起的 POST/PATCH/DELETE 不會帶上這個
    // cookie。因此所有會改變狀態的操作都**必須**用非 GET 方法 (本專案的 Server Action
    // 都是 POST, 符合這個前提)。若日後新增以 GET 觸發的變更操作, 這道防線就會失效。
    sameSite: "lax",
    path: "/",
    maxAge: getCookieMaxAgeSeconds(),
  })
}

/**
 * 清掉 session cookie (登出、token 失效時)。
 *
 * 只刪瀏覽器這一份, token 本身到期前仍然有效 —— 撤銷要由後端把世代號 +1 (登出、換密碼,
 * 見 docs/foundation/decisions.md 第 1 條), 這裡只是收尾。
 * 在 Server Component 的算繪階段呼叫會丟例外 (那時不允許寫 cookie), 呼叫端自己決定要不要接住。
 */
export async function clearAccessTokenCookie() {
  await deleteCookies(ACCESS_TOKEN_COOKIE)
}
