"use client"

import { useCallback, useState } from "react"

export type NotifyState = {
  open: boolean
  message: string
  severity?: "success" | "error" | "info" | "warning"
}

/**
 * 通知訊息的狀態容器。全站唯一一份 —— `(protected)` 與 `(public)` 都用這個。
 *
 * 回傳的函式都用 `useCallback` 包起來 (`setNotify` 本身是穩定的, 所以依賴為空陣列):
 * 這樣呼叫端把它們放進 `useEffect` 的依賴陣列時不會每次 render 都重跑。
 * 少了這一層, 呼叫端就得靠 eslint-disable 去繞過 exhaustive-deps, 那只是把問題藏起來。
 */
export function useNotify() {
  const [notify, setNotify] = useState<NotifyState>({ open: false, message: "" })

  const notifyError = useCallback((message: string) => {
    setNotify({ open: true, message, severity: "error" })
  }, [])

  const notifySuccess = useCallback((message: string) => {
    setNotify({ open: true, message, severity: "success" })
  }, [])

  const notifyInfo = useCallback((message: string) => {
    setNotify({ open: true, message, severity: "info" })
  }, [])

  const closeNotify = useCallback(() => {
    setNotify((prev) => ({ ...prev, open: false }))
  }, [])

  return { notify, setNotify, notifyError, notifySuccess, notifyInfo, closeNotify }
}
