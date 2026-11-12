/**
 * 「可以公開給瀏覽器」的部署設定, **執行期**才決定值: 伺服器端讀 `process.env`, 經 provider
 * 傳給 client。不用 `NEXT_PUBLIC_*`: 那會在 build 當下烤進 image, 改了主機 `.env` 不會生效。
 *
 * `API_URL` 刻意不放這裡 (那是內部拓撲); 版號跟 API 拿。
 */

export type PublicConfig = {
  /** 顯示在側欄、分頁標題與 PWA 名稱上的系統名稱 (`.env` 的 `SYSTEM_NAME`)。 */
  systemName: string
}

/**
 * 拿不到值時的退路。
 *
 * 新增欄位時先決定**空字串算不算有效設定**: 算的話用 `??`, 不算就用 `||` (`systemName`
 * 那樣, 空字串會讓側欄與標題整個消失)。搞反的症狀都是安靜地顯示錯的東西。
 */
export const FALLBACK_PUBLIC_CONFIG: PublicConfig = {
  systemName: "App",
}

/**
 * 只列出這個函式真的會讀的變數。index signature 是為了讓 `process.env` 傳得進來
 * (否則會撞上 TypeScript 的 weak type detection)。
 */
type PublicConfigEnv = {
  SYSTEM_NAME?: string
  [key: string]: string | undefined
}

/**
 * 純函式, 環境變數由呼叫端傳進來 (在 client 端讀 `process.env` 不會報錯, 只會永遠是 undefined)。
 * 真正的入口是帶 `server-only` 的 `./config.server.ts`; 邏輯留在這裡才測得到。
 */
export function readPublicConfig(env: PublicConfigEnv): PublicConfig {
  return {
    systemName: env.SYSTEM_NAME || FALLBACK_PUBLIC_CONFIG.systemName,
  }
}
