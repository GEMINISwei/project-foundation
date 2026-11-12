"use client"

import ErrorBoundary from "../error"

/**
 * `(user)`/`admin/` 共用的錯誤畫面, 兩區的 `error.tsx` 只轉出它。內容與根目錄的
 * `error.tsx` 相同, 只是畫成 inline —— 這層在 AppShell 內部, 外框已經撐滿視窗。
 *
 * 放在兩區各自的 error.tsx 而不是 `(protected)/error.tsx`: error boundary 只包住同層的頁面、
 * 不包同層的 layout, 放在上一層的話錯誤畫面會蓋掉外殼, 側欄跟著消失。
 */

type AreaErrorBoundaryProps = {
  error: Error & { digest?: string }
  reset: () => void
}

export default function AreaErrorBoundary(props: AreaErrorBoundaryProps) {
  return <ErrorBoundary {...props} inline />
}
