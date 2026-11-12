// 密碼規則。數字對應後端 users 模組的限制 (bcrypt 只看前 72 bytes), 登入、
// 個人設定與使用者管理都用這一份, 由 `public.client.ts` 對外。

import { translate } from "@/shared/i18n/dictionary"
import type { Locale } from "@/shared/i18n/locale"
import { authMessages } from "./i18n"

export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_BYTES = 72

function passwordBytes(value: string) {
  return new TextEncoder().encode(value).length
}

// 收 `locale` 而不是收一個 translator: 呼叫端手上的 translator 綁的是它自己模組的字典,
// key 對不上。收語系讓這兩支自己去查 auth 的字典, 呼叫端只要把 `useLocale()` 傳進來。
// 也不回傳 key 讓呼叫端自己翻譯 —— 那等於把「有哪些密碼錯誤」複製到每一個表單裡。

export function validateNewPassword(value: string, locale: Locale): string | undefined {
  const t = translate(authMessages, locale)

  if (!value) return t("passwordRequired")
  if (Array.from(value).length < MIN_PASSWORD_LENGTH) return t("passwordTooShort", { min: MIN_PASSWORD_LENGTH })
  if (passwordBytes(value) > MAX_PASSWORD_BYTES) return t("passwordTooLong", { max: MAX_PASSWORD_BYTES })
}

export function validateLoginPassword(value: string, locale: Locale): string | undefined {
  const t = translate(authMessages, locale)

  if (!value) return t("passwordRequired")
  if (passwordBytes(value) > MAX_PASSWORD_BYTES) return t("passwordTooLong", { max: MAX_PASSWORD_BYTES })
}
