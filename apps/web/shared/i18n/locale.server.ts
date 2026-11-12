// Server Component 與 Server Action 這一側的語系入口。
//
// 帶 `server-only` 而不是 `"use server"`: 這不是 Server Action, 只是伺服器端的讀取函式。
// 要寫入語系請用 `./actions.ts` 的 `setLocale` (具名、窄介面)。
import "server-only"

import { cookies } from "next/headers"
import { type Locale, DEFAULT_LOCALE, isLocale, LOCALE_COOKIE } from "./locale"
import { type Messages, type Translator, translate } from "./dictionary"

/**
 * 這次請求的語系。
 *
 * 只讀 cookie, 不讀 `Accept-Language` —— header 的那一步在 `proxy.ts` 做過了,
 * 而且只做一次 (沒有 cookie 時才做)。兩邊都讀的話, 使用者切成中文之後,
 * 瀏覽器語言是英文的頁面會在 proxy 沒攔到的路徑上跳回英文。
 */
export async function getLocale(): Promise<Locale> {
  const value = (await cookies()).get(LOCALE_COOKIE)?.value

  return isLocale(value) ? value : DEFAULT_LOCALE
}

/** Server Component 用的查字典函式: `const t = await getT(messages)`。 */
export async function getT<T extends Record<string, string>>(
  messages: Messages<T>
): Promise<Translator<T>> {
  return translate(messages, await getLocale())
}
