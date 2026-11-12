// 角色對話框的本機驗證。純函式, 理由同 `modules/users/validation.ts`。

import { translate } from "@/shared/i18n/dictionary"
import type { Locale } from "@/shared/i18n/locale"
import { rolesMessages } from "./i18n"

/** 角色名稱: 去掉頭尾空白後不可為空 (後端 `NonEmptyText` 同一條規則)。 */
export function validateRoleName(name: string, locale: Locale): string | undefined {
  return name.trim() ? undefined : translate(rolesMessages, locale)("nameRequired")
}
