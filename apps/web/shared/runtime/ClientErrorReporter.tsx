"use client"

import { useEffect } from "react"
import { reportClientError } from "./client-error"

// 同一個畫面最多回報這麼多次: 一個在迴圈裡丟錯的元件不該灌爆伺服器的 log。
const MAX_REPORTS = 5

/** 掛在 root layout: 把沒被接住的瀏覽器錯誤回報給伺服器。不渲染任何東西。 */
export function ClientErrorReporter() {
  useEffect(() => {
    let sent = 0

    function report(error: unknown) {
      if (sent >= MAX_REPORTS) return
      sent += 1
      const message = error instanceof Error ? error.message : String(error)
      const stack = error instanceof Error ? error.stack : undefined
      // 回報本身失敗就算了, 不能再丟出一個錯誤。
      reportClientError({ message, stack, path: window.location.pathname }).catch(() => {})
    }

    const onError = (event: ErrorEvent) => report(event.error ?? event.message)
    const onRejection = (event: PromiseRejectionEvent) => report(event.reason)
    window.addEventListener("error", onError)
    window.addEventListener("unhandledrejection", onRejection)
    return () => {
      window.removeEventListener("error", onError)
      window.removeEventListener("unhandledrejection", onRejection)
    }
  }, [])

  return null
}
