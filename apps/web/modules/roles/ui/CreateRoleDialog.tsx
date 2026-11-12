"use client"

import { type FormEvent, useState } from "react"
import { FormDialog, TextInput, useActionSubmit } from "@/shared/ui"
import { useLocale, useT } from "@/shared/i18n/context"
import { rolesMessages } from "../i18n"
import { validateRoleName } from "../validation"
import { createRole } from "../actions"

type CreateRoleDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export default function CreateRoleDialog({
  open,
  onClose,
  onSuccess,
  onError,
}: CreateRoleDialogProps) {
  const t = useT(rolesMessages)
  const locale = useLocale()
  const [nameError, setNameError] = useState<string>()
  const [name, setName] = useState("")
  const { isPending, submit, fieldError, clearFieldErrors } = useActionSubmit()

  function resetState() {
    setName("")
    setNameError(undefined)
    clearFieldErrors()
  }

  function handleClose() {
    resetState()
    onClose()
  }

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextError = validateRoleName(name, locale)
    setNameError(nextError)
    if (nextError) return

    submit(
      () => createRole({ name: name.trim() }),
      {
        onSuccess: () => {
          resetState()
          onSuccess(t("roleCreated"))
        },
        onError,
        errorFallback: t("createFailed"),
      }
    )
  }

  return (
    <FormDialog title={t("create")} open={open} isPending={isPending} submitText={t("createSubmit")} pendingText={t("createPending")} onClose={handleClose} onSubmit={submitCreate}>
      <TextInput label={t("colName")} value={name} error={nameError ?? fieldError("name")} required disabled={isPending} autoFocus onChange={setName} />
    </FormDialog>
  )
}
