"use client"

import { useEffect, useRef, useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { errorMessage } from "@/shared/api/result"
import { createActionFormData } from "@/shared/api/action-form-data"
import { useLocale, useT } from "@/shared/i18n/context"
import { LOGIN_PATH, LOGIN_REDIRECT_REASONS } from "@/shared/session/login-contract"
import { useNotify } from "@/shared/ui"
import { loginUser } from "../actions"
import { authMessages } from "../i18n"
import { LOGIN_REDIRECT_MESSAGE_KEYS } from "../constants"
import { validateLoginValues } from "../validation"
import type { LoginFormErrors, LoginFormValues, LoginRedirectReason } from "../types"

const initialValues: LoginFormValues = {
  username: "",
  password: "",
}

type UseLoginFormParams = {
  reason?: LoginRedirectReason
}

export function useLoginForm({ reason }: UseLoginFormParams) {
  const locale = useLocale()
  const t = useT(authMessages)
  const router = useRouter()
  const [values, setValues] = useState<LoginFormValues>(initialValues)
  const [errors, setErrors] = useState<LoginFormErrors>({})
  const [isSubmit, setIsSubmit] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isPending, startTransition] = useTransition()
  // 同 shared/ui 的 useActionSubmit: isPending 要等重新渲染才生效, 連按 Enter 要另外同步擋。
  const inFlight = useRef(false)
  // 登入與註冊共用通知狀態管理。
  const { notify, notifyError, closeNotify } = useNotify()

  useEffect(() => {
    if (reason !== LOGIN_REDIRECT_REASONS.sessionExpired) return

    notifyError(t(LOGIN_REDIRECT_MESSAGE_KEYS[reason]))
    router.replace(LOGIN_PATH)
    // t 每次 render 都是新的函式 (translate 回傳新 closure), 放進依賴會讓這個
    // effect 每次都重跑並不斷 replace 網址。原因只跟 reason 有關, 依賴就只列它。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reason, router, notifyError])

  return {
    values,
    errors,
    isSubmit,
    isPending,
    showPassword,
    notifyState: notify,
    closeNotify,
    changeValue: (name: keyof LoginFormValues, value: string) => {
      const nextValues = {
        ...values,
        [name]: value,
      }

      setValues(nextValues)

      if (isSubmit) {
        setErrors(validateLoginValues(nextValues, locale))
      }
    },
    togglePassword: () => setShowPassword((prev) => !prev),
    submit: () => {
      const nextErrors = validateLoginValues(values, locale)
      setErrors(nextErrors)
      setIsSubmit(true)

      if (Object.values(nextErrors).some(Boolean)) return
      if (inFlight.current) return
      inFlight.current = true

      startTransition(async () => {
        let res: Awaited<ReturnType<typeof loginUser>>
        try {
          res = await loginUser(createActionFormData(values))
        } finally {
          inFlight.current = false
        }

        if (res.ok) {
          router.push("/")

          return
        }

        notifyError(errorMessage(res, t("loginFailed")))
      })
    },
  }
}
