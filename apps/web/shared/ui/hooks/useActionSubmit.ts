"use client"

import { useRef, useState, useTransition } from "react"
import { errorMessage, fieldErrors as fieldErrorsOf } from "@/shared/api/result"
import { useT } from "@/shared/i18n/context"
import type { ApiResult } from "@/shared/api/types"
import { uiMessages } from "../i18n"

function isNextNavigation(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("digest" in error)) return false
  return String(error.digest).startsWith("NEXT_")
}

export function useActionSubmit() {
  const t = useT(uiMessages)
  const [isPending, startTransition] = useTransition()
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  // isPending 要等重新渲染才生效, 連按 Enter 或連點的第二個事件可能在那之前就到了,
  // 所以另外用 ref 同步擋。
  const inFlight = useRef(false)

  function submit(
    run: () => Promise<ApiResult<unknown>>,
    options: {
      onSuccess: () => void
      onError: (message: string) => void
      errorFallback?: string
    }
  ) {
    if (inFlight.current) return
    inFlight.current = true
    setFieldErrors({})
    startTransition(async () => {
      let res: ApiResult<unknown>
      try {
        res = await run()
      } catch (error) {
        // Next 用例外來導向 (登入失效時導回登入頁), 那種要原樣放行。
        if (isNextNavigation(error)) throw error
        // 動作本身沒有回應 (斷線、伺服器重啟中): 顯示錯誤, 不讓畫面停在沒有任何提示的狀態。
        options.onError(options.errorFallback ?? t("actionFailed"))
        return
      } finally {
        inFlight.current = false
      }

      if (res.ok) {
        options.onSuccess()
        return
      }

      setFieldErrors(fieldErrorsOf(res))
      options.onError(errorMessage(res, options.errorFallback ?? t("actionFailed")))
    })
  }

  // key 就是後端回傳的欄位名 (ErrorBody.fields), 這一層不做任何字串加工。
  function fieldError(name: string): string | undefined {
    return fieldErrors[name]
  }

  function clearFieldErrors() {
    setFieldErrors({})
  }

  return { isPending, submit, fieldError, clearFieldErrors }
}
