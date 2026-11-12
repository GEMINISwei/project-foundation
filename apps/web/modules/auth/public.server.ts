import "server-only"
/**
 * auth 模組的 Server 公開面。
 *
 * 網頁上刻意沒有註冊頁: 超級管理者只能用 `make db superuser` 建立, 一般帳號由超管在後台建立。
 * 繼承的專案需要自助註冊時, 頁面加在這個模組並從這裡匯出。
 *
 * auth 沒有「模組主頁」, 所以頁面用 `<name>-page.server.tsx` 命名 (有主頁的
 * 模組是 `page.server.tsx` + `<name>-page.server.tsx`, 例見 `modules/roles`)。
 */

export { default as LoginPage, generateMetadata as generateLoginMetadata } from "./login-page.server"
export type { LoginPageProps } from "./login-page.server"
export { getCurrentUser, requirePermission } from "./current-user.server"
