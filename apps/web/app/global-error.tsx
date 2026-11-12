"use client"

import { MessagePage, MessagePageButton } from "@/shared/ui"
import { translate } from "@/shared/i18n/dictionary"
import { useLocaleFromCookie } from "@/shared/i18n/context"
import { HTML_LANG } from "@/shared/i18n/locale"
import { appMessages } from "@/config/i18n"
// 樣式要在這裡再載一次, 順序同 layout.tsx。這一頁**取代** root layout, 所以 layout.tsx 的
// CSS import 不會出現在它的文件裡 —— 少了這幾行, `var(--…)` 解不出來、MessagePage 的 class
// 也沒有規則, 錯誤頁會退回瀏覽器預設樣式。
import "./theme.css"
import "@/shared/ui/styles/base.css"
import "@/shared/ui/styles/message-page.css"

type GlobalErrorProps = {
  error: Error & { digest?: string }
  reset: () => void
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  // 這一頁在 root layout 之外渲染, 拿不到 LocaleProvider, 所以直接讀 cookie。
  const locale = useLocaleFromCookie()
  const t = translate(appMessages, locale)
  // 同 error.tsx: 只有伺服器端的錯誤有 digest。
  const reference = error.digest ? t("errorReference", { digest: error.digest }) : undefined

  return (
    <html lang={HTML_LANG[locale]}>
      <body>
        <MessagePage title={t("errorTitle")} description={t("errorDescription")} reference={reference}>
          <MessagePageButton onClick={reset}>{t("retry")}</MessagePageButton>
        </MessagePage>
      </body>
    </html>
  )
}
