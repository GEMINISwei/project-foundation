"use client"

import { useT } from "@/shared/i18n/context"
import { settingsMessages } from "../i18n"
import styles from "./settings.module.css"

export default function AboutSettings({ version }: { version: string }) {
  const t = useT(settingsMessages)

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{t("aboutSection")}</h2>
      <div className={styles.settingRow}>
        <div className={styles.settingInfo}>
          <span className={styles.settingName}>{t("systemVersion")}</span>
        </div>
        <span className={styles.settingValue}>{version}</span>
      </div>
    </section>
  )
}
