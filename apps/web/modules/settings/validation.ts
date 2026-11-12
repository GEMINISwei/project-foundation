// 設定頁表單的驗證。純函式 (收 `locale` 而不是收 translator), 所以測得到 ——
// 欄位之間的關係就在這裡, `ui/` 只負責畫面與狀態。

import { translate } from "@/shared/i18n/dictionary"
import type { Locale } from "@/shared/i18n/locale"
import { validateLoginPassword, validateNewPassword } from "@/modules/auth/public.client"
import { settingsMessages } from "./i18n"
import type { PasswordFormErrors, PasswordFormValues } from "./types"

/** 暱稱: 去掉頭尾空白後不可為空 (後端 `NonEmptyText` 同一條規則)。 */
export function validateNickname(nickname: string, locale: Locale): string | undefined {
  return nickname.trim() ? undefined : translate(settingsMessages, locale)("nicknameRequired")
}

export function validatePasswordValues(
  values: PasswordFormValues,
  locale: Locale,
): PasswordFormErrors {
  const t = translate(settingsMessages, locale)
  const errors: PasswordFormErrors = {}

  // 舊密碼只檢查「有沒有填」與 bcrypt 的長度上限, **不套強度規則** —— 它可能是規則變嚴
  // 之前設的, 拿新規則擋它會讓最該換密碼的那批人反而換不了。後端的 `PasswordChange`
  // 是同一個分法 (`Password` vs `NewPassword`), 兩邊要一致。
  errors.current_password = validateLoginPassword(values.current_password, locale)
  errors.new_password = validateNewPassword(values.new_password, locale)

  // 這一條是 UX 護欄不是安全規則, 所以後端沒有對應的檢查: 送一把跟原本相同的密碼上去
  // 不會造成任何問題, 只是使用者八成不是這個意思。
  if (!errors.new_password && values.new_password === values.current_password) {
    errors.new_password = t("passwordSameAsCurrent")
  }

  // 確認欄位只在新密碼本身過得了的時候才比對: 兩個錯誤同時亮起來, 使用者不知道要先改哪個。
  if (!errors.new_password && values.confirm_password !== values.new_password) {
    errors.confirm_password = t("passwordMismatch")
  }

  return errors
}
