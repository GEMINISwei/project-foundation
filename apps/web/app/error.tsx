"use client"

import { MessagePage, MessagePageButton, MessagePageLink } from "@/shared/ui"
import { useT } from "@/shared/i18n/context"
import { appMessages } from "@/config/i18n"

type ErrorBoundaryProps = {
  error: Error & { digest?: string }
  reset: () => void
  /** 畫在外殼裡面時用 (見 `(protected)/area-error.tsx`)。Next 不會傳這個值。 */
  inline?: boolean
}

export default function ErrorBoundary({ error, reset, inline = false }: ErrorBoundaryProps) {
  const t = useT(appMessages)
  // 只有伺服器端的錯誤有 digest; 瀏覽器端的錯誤沒有伺服器 log 可查, 也就不顯示。
  const reference = error.digest ? t("errorReference", { digest: error.digest }) : undefined

  return (
    <MessagePage
      inline={inline}
      title={t("pageErrorTitle")}
      description={t("pageErrorDescription")}
      reference={reference}
    >
      <MessagePageButton onClick={reset}>{t("reload")}</MessagePageButton>
      <MessagePageLink href="/">{t("backHome")}</MessagePageLink>
    </MessagePage>
  )
}
