"use client"

import { type FormEvent, useState } from "react"
import { FormDialog, SelectInput, TextInput, useActionSubmit } from "@/shared/ui"
import { useLocale, useT } from "@/shared/i18n/context"
import { createActionFormData } from "@/shared/api/action-form-data"
import { usersMessages } from "../i18n"
import { createUser } from "../actions"
import { validateCreateUserValues } from "../validation"

type CreateUserDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
  roleOptions: Array<{ value: string; label: string }>
}

export default function CreateUserDialog({
  open,
  onClose,
  onSuccess,
  onError,
  roleOptions,
}: CreateUserDialogProps) {
  const t = useT(usersMessages)
  const locale = useLocale()
  const [username, setUsername] = useState("")
  const [nickname, setNickname] = useState("")
  const [password, setPassword] = useState("")
  const [selectedRoleId, setSelectedRoleId] = useState("")
  const [errors, setErrors] = useState<ReturnType<typeof validateCreateUserValues>>({})
  const { isPending, submit, fieldError, clearFieldErrors } = useActionSubmit()

  function resetState() {
    setUsername("")
    setNickname("")
    setPassword("")
    setSelectedRoleId("")
    setErrors({})
    clearFieldErrors()
  }

  function handleClose() {
    resetState()
    onClose()
  }

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateCreateUserValues({ username, nickname, password }, locale)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return

    submit(
      () => createUser(createActionFormData({
        username: username.trim(),
        nickname: nickname.trim(),
        password,
        role_ids: selectedRoleId ? [selectedRoleId] : [],
      })),
      {
        onSuccess: () => {
          resetState()
          onSuccess(t("userCreated"))
        },
        onError,
        errorFallback: t("createFailed"),
      }
    )
  }

  return (
    <FormDialog title={t("create")} open={open} isPending={isPending} submitText={t("createSubmit")} pendingText={t("createPending")} onClose={handleClose} onSubmit={submitCreate}>
      <TextInput label={t("colNickname")} value={nickname} error={errors.nickname ?? fieldError("nickname")} required disabled={isPending} autoFocus onChange={setNickname} />
      <TextInput label={t("colUsername")} value={username} error={errors.username ?? fieldError("username")} required disabled={isPending} autoComplete="off" onChange={setUsername} />
      <TextInput label={t("password")} type="password" autoComplete="new-password" value={password} error={errors.password ?? fieldError("password")} required disabled={isPending} onChange={setPassword} />
      {roleOptions.length > 0 && (
        <SelectInput
          label={t("colRole")}
          value={selectedRoleId}
          error={fieldError("role_ids")}
          disabled={isPending}
          options={[{ value: "", label: t("roleUnassigned") }, ...roleOptions]}
          onChange={setSelectedRoleId}
        />
      )}
    </FormDialog>
  )
}
