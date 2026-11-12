"use client"

import { type FormEvent, useState } from "react"
import { FormDialog, TextInput, useActionSubmit } from "@/shared/ui"
import { useLocale, useT } from "@/shared/i18n/context"
import { createActionFormData } from "@/shared/api/action-form-data"
import { usersMessages } from "../i18n"
import { resetUserPassword } from "../actions"
import { validateResetPassword } from "../validation"
import type { UserInfo } from "../types"

type ResetPasswordDialogProps = {
  user: UserInfo | null
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export default function ResetPasswordDialog({
  user,
  onClose,
  onSuccess,
  onError,
}: ResetPasswordDialogProps) {
  const t = useT(usersMessages)
  const locale = useLocale()
  const [password, setPassword] = useState("")
  const [passwordError, setPasswordError] = useState<string>()
  const { isPending, submit, fieldError, clearFieldErrors } = useActionSubmit()

  function resetState() {
    setPassword("")
    setPasswordError(undefined)
    clearFieldErrors()
  }

  function handleClose() {
    resetState()
    onClose()
  }

  function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!user) {
      onError(t("selectUserRequired"))
      return
    }
    const nextError = validateResetPassword(password, locale).password
    setPasswordError(nextError)
    if (nextError) return

    submit(
      () => resetUserPassword(createActionFormData({ id: user.id, password })),
      {
        onSuccess: () => {
          resetState()
          onSuccess(t("passwordReset"))
        },
        onError,
        errorFallback: t("resetPasswordFailed"),
      }
    )
  }

  return (
    <FormDialog title={t("resetPassword")} open={user !== null} isPending={isPending} submitText={t("resetPassword")} onClose={handleClose} onSubmit={submitReset}>
      <p>{t("resetPasswordFor", { nickname: user?.nickname ?? "" })}</p>
      <TextInput label={t("newPassword")} type="password" autoComplete="new-password" value={password} error={passwordError ?? fieldError("password")} required disabled={isPending} autoFocus onChange={setPassword} />
    </FormDialog>
  )
}
