// 後台使用者對話框的本機驗證。純函式 (收 `locale` 而不是收 translator), 所以測得到;
// 錯誤按欄位回傳, 由 `ui/` 標在出錯的那一格, 不只丟一則會消失的 toast。

import { translate } from "@/shared/i18n/dictionary"
import type { Locale } from "@/shared/i18n/locale"
import { validateNewPassword } from "@/modules/auth/public.client"
import { usersMessages } from "./i18n"

type CreateUserValues = { username: string; nickname: string; password: string }
type CreateUserErrors = Partial<Record<keyof CreateUserValues, string>>

export function validateCreateUserValues(
  values: CreateUserValues,
  locale: Locale,
): CreateUserErrors {
  const t = translate(usersMessages, locale)
  return {
    username: values.username.trim() ? undefined : t("usernameRequired"),
    nickname: values.nickname.trim() ? undefined : t("nicknameRequired"),
    password: validateNewPassword(values.password, locale),
  }
}

export function validateResetPassword(password: string, locale: Locale): { password?: string } {
  return { password: validateNewPassword(password, locale) }
}

export function validateEditUserValues(
  values: { nickname: string },
  locale: Locale,
): { nickname?: string } {
  const t = translate(usersMessages, locale)
  return { nickname: values.nickname.trim() ? undefined : t("nicknameRequired") }
}
