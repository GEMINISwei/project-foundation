"use client"

import { useTransition } from "react"
import { setLocale } from "@/shared/i18n/actions"
import { useLocale, useT } from "@/shared/i18n/context"
import { type Locale, SUPPORTED_LOCALES } from "@/shared/i18n/locale"
import { SelectInput } from "@/shared/ui"
import { settingsMessages } from "../i18n"
import styles from "./settings.module.css"

// 語系代號 → 顯示名稱的字典 key。兩種語言的選項在**任何**語系下都用它自己的語言呈現
// (「繁體中文」永遠是「繁體中文」), 這是語言選擇器的通則: 使用者要能認得自己的語言。
const LOCALE_LABEL_KEYS = {
  zh: "localeZh",
  en: "localeEn",
} as const satisfies Record<Locale, keyof (typeof settingsMessages)["zh"]>

export default function LanguageSettings() {
  const t = useT(settingsMessages)
  const locale = useLocale()
  const [isPending, startTransition] = useTransition()

  function changeLocale(next: string) {
    if (next === locale) return
    // setLocale 會 revalidate 整個 layout, 所以不需要自己 router.refresh()。
    startTransition(() => setLocale(next as Locale))
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{t("languageSection")}</h2>
      <div className={styles.settingRow}>
        <div className={styles.settingInfo}>
          <span className={styles.settingName}>{t("languageName")}</span>
          <span className={styles.settingDesc}>{t("languageDesc")}</span>
        </div>
        <div className={styles.settingAction}>
          <SelectInput
            ariaLabel={t("languageName")}
            value={locale}
            disabled={isPending}
            onChange={changeLocale}
            options={SUPPORTED_LOCALES.map((value) => ({
              value,
              label: t(LOCALE_LABEL_KEYS[value]),
            }))}
          />
        </div>
      </div>
    </section>
  )
}
