import type { Metadata, Viewport } from "next"
import { NotifyViewport } from "@/shared/ui"
import { HTML_LANG } from "@/shared/i18n/locale"
import { getLocale } from "@/shared/i18n/locale.server"
import { LocaleProvider } from "@/shared/i18n/context"
import { getPublicConfig } from "@/shared/runtime/config.server"
import { PublicConfigProvider } from "@/shared/runtime/context"
import { ClientErrorReporter } from "@/shared/runtime/ClientErrorReporter"
// 順序有意義: UI kit 的預設變數 → 專案的覆寫 → reset。
// 設計變數: theme.css 會先載入 tokens.css 的預設值再覆寫 (理由見 theme.css 檔頭)。
import "./theme.css"
import "@/shared/ui/styles/base.css"
import "@/shared/ui/styles/message-page.css"

// 手機上畫面不能縮放, 手感才像原生 App; 代價與擋不到的情況見 docs/foundation/decisions.md 第 14 條。
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

// 用 `generateMetadata` 而不是靜態的 `metadata`: 標題來自執行期的環境變數, 而靜態 metadata 會
// 在預先渲染的頁面上於 build 期定案 (同 `shared/runtime/config.ts` 要解決的問題)。
export async function generateMetadata(): Promise<Metadata> {
  const { systemName } = getPublicConfig()

  return {
    title: {
      default: systemName,
      template: `%s | ${systemName}`,
    },
    description: "",
    icons: {
      icon: [
        { url: "/favicon.ico", sizes: "any" },
        { url: "/app-icon-192.png", sizes: "192x192", type: "image/png" },
        { url: "/app-icon-512.png", sizes: "512x512", type: "image/png" },
      ],
      apple: [
        { url: "/app-icon-192.png", sizes: "192x192" },
        { url: "/app-icon-1024.png", sizes: "1024x1024" },
      ],
    },
  }
}

export default async function RootLayout({ children }: React.PropsWithChildren) {
  const locale = await getLocale()
  const publicConfig = getPublicConfig()

  return (
    <html lang={HTML_LANG[locale]}>
      <body>
        {/* provider 只帶語系代號, 字典由各元件自己 import (見 shared/i18n/context.tsx)。 */}
        <LocaleProvider locale={locale}>
          {/* 公開設定只有這一個注入點; client component 一律走 usePublicConfig()。 */}
          <PublicConfigProvider config={publicConfig}>
            {children}
            <NotifyViewport />
            <ClientErrorReporter />
          </PublicConfigProvider>
        </LocaleProvider>
      </body>
    </html>
  )
}
