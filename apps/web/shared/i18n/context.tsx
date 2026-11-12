"use client"

/**
 * client component 這一側的語系入口。
 *
 * context 裡只放**語系代號**, 不放字典: 字典由各元件自己 import (`useT(messages)`), bundler
 * 才只打包用到的那幾份。塞進 provider 的話, root layout 會變成所有模組字串的匯流點, 等於在
 * RSC payload 裡送一份全站文案。
 */

import { createContext, use, useSyncExternalStore } from "react"
import { type Locale, DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "./locale"
import { type Messages, type Translator, translate } from "./dictionary"

const LocaleContext = createContext<Locale>(DEFAULT_LOCALE)

export function LocaleProvider({
  locale,
  children,
}: {
  locale: Locale
  children: React.ReactNode
}) {
  return <LocaleContext value={locale}>{children}</LocaleContext>
}

export function useLocale(): Locale {
  return use(LocaleContext)
}

/** client component 用的查字典函式: `const t = useT(messages)`。 */
export function useT<T extends Record<string, string>>(messages: Messages<T>): Translator<T> {
  return translate(messages, useLocale())
}

function readLocaleCookie(): Locale {
  const value = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${LOCALE_COOKIE}=`))
    ?.slice(LOCALE_COOKIE.length + 1)

  return isLocale(value) ? value : DEFAULT_LOCALE
}

// 不訂閱任何東西: 這個 hook 的使用者是錯誤頁, 語系在那一頁的存活期間不會變。
const NEVER_CHANGES = () => () => {}

/**
 * 直接從 cookie 讀語系, 給**拿不到 provider** 的地方用。目前唯一的使用者是
 * `app/global-error.tsx` —— 它在 root layout 之外渲染, context 不存在。
 *
 * 用 `useSyncExternalStore` 而不是 `useState` + `useEffect`: 伺服器端沒有 `document`, 兩份
 * snapshot 分開給才能同時做到「SSR 用預設值」與「client 直接讀到正確值」, 不會 hydration
 * mismatch 也不會多一次 render。
 *
 * 這是 `setLocale` 把 cookie 設成非 httpOnly 的理由 —— 沒有它, 這一頁只能寫死語言。
 */
export function useLocaleFromCookie(): Locale {
  return useSyncExternalStore(NEVER_CHANGES, readLocaleCookie, () => DEFAULT_LOCALE)
}
