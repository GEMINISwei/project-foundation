"use client"

import { useRouter } from "next/navigation"
import { useNotify } from "./useNotify"

export function useListFeedback(onSuccessCleanup?: () => void) {
  const router = useRouter()
  const { notify, notifyError, notifySuccess, notifyInfo, closeNotify } = useNotify()

  function handleSuccess(message: string) {
    onSuccessCleanup?.()
    notifySuccess(message)
    router.refresh()
  }

  function handleError(message: string) {
    notifyError(message)
  }

  return { notify, closeNotify, handleSuccess, handleError, notifySuccess, notifyError, notifyInfo }
}
