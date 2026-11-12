"use client"

import { type FormEvent, useState } from "react"
import { FormDialog, SelectInput, TextInput, useActionSubmit, useActiveStatusOptions } from "@/shared/ui"
import { useLocale, useT } from "@/shared/i18n/context"
import { rolesMessages } from "../i18n"
import { validateRoleName } from "../validation"
import { updateRole } from "../actions"
import type { RoleInfo } from "../types"

type EditRoleDialogProps = {
  role: RoleInfo | null
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export default function EditRoleDialog({ role, onClose, onSuccess, onError }: EditRoleDialogProps) {
  const t = useT(rolesMessages)
  const locale = useLocale()
  const [nameError, setNameError] = useState<string>()
  const statusOptions = useActiveStatusOptions()
  const [editName, setEditName] = useState(role?.name ?? "")
  const [editIsDisabled, setEditIsDisabled] = useState(role?.is_disabled ?? false)
  const { isPending, submit, fieldError } = useActionSubmit()

  function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!role) return
    const nextError = validateRoleName(editName, locale)
    setNameError(nextError)
    if (nextError) return

    submit(
      () => updateRole(role.id, {
        name: editName.trim(),
        permissions: role.permissions,
        is_disabled: editIsDisabled,
      }),
      {
        onSuccess: () => onSuccess(t("roleUpdated")),
        onError,
        errorFallback: t("updateFailed"),
      }
    )
  }

  return (
    <FormDialog title={t("editTitle")} open={role !== null} isPending={isPending} submitText={t("editSubmit")} pendingText={t("editPending")} onClose={onClose} onSubmit={submitEdit}>
      <TextInput label={t("colName")} value={editName} error={nameError ?? fieldError("name")} required disabled={isPending} autoFocus onChange={setEditName} />
      <SelectInput
        label={t("colStatus")}
        value={editIsDisabled ? "disabled" : "active"}
        error={fieldError("is_disabled")}
        disabled={isPending || Boolean(role?.code)}
        options={statusOptions}
        onChange={(value) => setEditIsDisabled(value === "disabled")}
      />
    </FormDialog>
  )
}
