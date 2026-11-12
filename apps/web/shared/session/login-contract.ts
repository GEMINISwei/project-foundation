/**
 * 登入入口的約定: shared、`proxy.ts`、受保護區的 layout 與 auth 模組共用的名字。
 *
 * 分散各寫一份的話, 改名時漏一處的症狀是「登入了卻被當成沒登入」或「被導到不存在的頁面」,
 * 都不會有錯誤訊息。集中在這裡, 也讓 shared 對專案的要求寫成程式碼: **專案要在 `LOGIN_PATH`
 * 提供登入頁, 並認得 `?reason=` 帶來的導向原因** (由 `modules/auth` 提供)。
 *
 * 這支會被 `proxy.ts` 在 edge runtime 載入, 不可引用任何東西。
 */

/** 存放後端 JWT 的 httpOnly cookie。寫入與刪除都在 `access-token.server.ts`。 */
export const ACCESS_TOKEN_COOKIE = "access_token"

export const LOGIN_PATH = "/login"

/** 被導回登入頁的原因, 登入頁據此顯示說明。 */
export const LOGIN_REDIRECT_REASONS = {
  sessionExpired: "session-expired",
} as const

type RedirectReasons = typeof LOGIN_REDIRECT_REASONS

export type LoginRedirectReason = RedirectReasons[keyof RedirectReasons]

export function loginUrl(reason?: LoginRedirectReason): string {
  return reason ? `${LOGIN_PATH}?reason=${reason}` : LOGIN_PATH
}
