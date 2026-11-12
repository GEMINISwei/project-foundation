"use client"

import { MessagePage, MessagePageLink } from "@/shared/ui"
import { useT } from "@/shared/i18n/context"
import { appMessages } from "@/config/i18n"

/**
 * 404 的畫面本體。
 *
 * 與 `not-found.tsx` 分開的原因: 那一支必須是 Server Component (`generateMetadata` 只能
 * 從伺服器端匯出), 而拿語系要 `await`, async Server Component 沒辦法在單元測試裡渲染。
 * 拆出這一層之後, 標題留在伺服器端、畫面可以被測試直接掛起來。
 *
 * 這個檔名不是 App Router 的慣例檔, 不會被當成路由。
 */
export default function NotFoundView() {
  const t = useT(appMessages)

  return (
    <MessagePage title={t("notFoundTitle")} description={t("notFoundDescription")}>
      <MessagePageLink href="/">{t("backHome")}</MessagePageLink>
    </MessagePage>
  )
}
