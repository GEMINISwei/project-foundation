import Link from "next/link"
import type { ReactNode } from "react"

// 全頁訊息 (錯誤、404) 的共用外觀。樣式由 root layout 載入, 避免 Next.js dev
// 將共用 CSS 拆成 error/not-found 專屬 preload chunk。
// app/global-error.tsx 取代整個 root layout, 拿不到 layout 的 CSS, 所以它自己再載一次同一組樣式表。

type MessagePageProps = {
  title: string
  description: string
  /** 巢狀在 AppShell 內時用 true: 外層已經撐滿視窗, 這裡只要填滿容器。 */
  inline?: boolean
  /** 給使用者回報用的代碼 (例: 錯誤代碼), 顯示在按鈕下方。 */
  reference?: string
  children?: ReactNode
}

export function MessagePage({ title, description, inline, reference, children }: MessagePageProps) {
  // 整頁時它自己就是頁面主體 (main 地標); inline 時畫在外殼的 <main> 裡, 再出一個就是兩個主要地標。
  const Root = inline ? "div" : "main"

  return (
    <Root className={`message-page${inline ? " message-page--inline" : ""}`}>
      <section className="message-page__panel">
        <h2 className="message-page__title">{title}</h2>
        <p className="message-page__description">{description}</p>
        <div className="message-page__actions">{children}</div>
        {reference && <p className="message-page__reference">{reference}</p>}
      </section>
    </Root>
  )
}

export function MessagePageButton({
  onClick,
  children,
}: {
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="message-page__action message-page__action--primary"
    >
      {children}
    </button>
  )
}

export function MessagePageLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="message-page__action message-page__action--secondary">
      {children}
    </Link>
  )
}
