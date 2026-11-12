/**
 * 語系的基本定義。**這個檔案必須保持 edge-safe** —— `proxy.ts` 與每個模組的 `manifest.ts`
 * 都會用到它, 一旦 import 了 react/next/server-only, 那兩處會直接壞掉 (dependency-cruiser 的
 * `manifest-is-edge-safe` 會順著 manifest 的間接依賴檢查到這裡)。`import type` 編譯後會被抹掉, 不影響這件事。
 *
 * 所以這裡只有型別、常數與純函式; 讀 cookie 在 `locale.server.ts`, React 那一半在 `context.tsx`。
 */

import type { Language } from "@/shared/api/types"

/**
 * 支援的語系。**唯一來源是後端**的 `Language` enum, 經由 OpenAPI 產生。
 *
 * 這裡多留一份執行期陣列, 是因為型別在執行期不存在, 而 proxy 的比對與設定頁的下拉選單都需要
 * 能迭代的值。一致性由 `satisfies` 加 `tests/shared/i18n/locale.test-d.ts` 的雙向斷言擋著。
 */
export const SUPPORTED_LOCALES = ["zh", "en"] as const satisfies readonly Language[]

export type Locale = Language

export const DEFAULT_LOCALE: Locale = "zh"

/** 存放使用者選擇的 cookie 名稱。proxy、Server Component 與 Server Action 共用這一個。 */
export const LOCALE_COOKIE = "locale"

/**
 * `<html lang>` 用的 BCP 47 標籤。跟 `Locale` 分開: 送給後端的是 `zh` (後端只認前綴, 見
 * `resolve_language()`), 但 `lang` 屬性要夠精確 —— 瀏覽器的字型選擇與斷行規則會看它,
 * 標 `zh` 在某些環境會落到簡體字型。
 */
export const HTML_LANG: Record<Locale, string> = {
  zh: "zh-Hant",
  en: "en",
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

/**
 * 從 `Accept-Language` 挑出支援的語系, 判斷不出來就回傳預設值。
 *
 * 行為刻意與後端 `shared/i18n.py` 的 `resolve_language()` 一致 (只做前綴比對、不處理
 * q 權重): 兩邊不一致會出現「UI 是中文但錯誤訊息是英文」這種只在特定瀏覽器設定下才重現的
 * 錯誤。`tests/shared/i18n/locale.test.ts` 用與後端測試相同的案例釘住它。
 */
export function resolveLocale(acceptLanguage: string | null | undefined): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE

  for (const part of acceptLanguage.split(",")) {
    const tag = part.split(";")[0].trim().toLowerCase()
    const primary = tag.split("-")[0]
    if (isLocale(primary)) return primary
  }

  return DEFAULT_LOCALE
}

/** 一段文字的中英兩份。對應後端的 `LangText`, 用在字典裝不下的地方 (例如 manifest)。 */
export type LocaleText = Record<Locale, string>
