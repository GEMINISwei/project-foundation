"use client"

import { type FormEvent, useState } from "react"
import { FormDialog, SelectInput, TextInput, useActionSubmit, useActiveStatusOptions } from "@/shared/ui"
import { useLocale, useT } from "@/shared/i18n/context"
import { usersMessages } from "../i18n"
import { updateUser } from "../actions"
import { getUserActions, roleIdsForUpdate } from "../capabilities"
import { validateEditUserValues } from "../validation"
import type { UserInfo } from "../types"

type EditUserDialogProps = {
  user: UserInfo | null
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
  currentUserId: string | undefined
  roleOptions: Array<{ value: string; label: string }>
}

export default function EditUserDialog({
  user,
  onClose,
  onSuccess,
  onError,
  currentUserId,
  roleOptions,
}: EditUserDialogProps) {
  const t = useT(usersMessages)
  const locale = useLocale()
  const statusOptions = useActiveStatusOptions()
  const [nickname, setNickname] = useState(user?.nickname ?? "")
  const [isDisabled, setIsDisabled] = useState(user?.is_disabled ?? false)
  const [selectedRoleId, setSelectedRoleId] = useState(user?.roles[0]?.id ?? "")
  const [nicknameError, setNicknameError] = useState<string>()
  const { isPending, submit, fieldError } = useActionSubmit()
  const { canAssignRole, canToggleStatus } = user
    ? getUserActions(user, currentUserId, true, roleOptions.length > 0)
    : { canAssignRole: false, canToggleStatus: false }

  function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!user) return
    const nextError = validateEditUserValues({ nickname }, locale).nickname
    setNicknameError(nextError)
    if (nextError) return

    submit(
      () => updateUser(user.id, {
        nickname: nickname.trim(),
        is_disabled: isDisabled,
        role_ids: roleIdsForUpdate(
          canAssignRole,
          selectedRoleId,
          user.roles.map((role) => role.id),
        ),
      }),
      {
        onSuccess: () => onSuccess(t("userUpdated")),
        onError,
        errorFallback: t("updateFailed"),
      }
    )
  }

  return (
    <FormDialog
      title={t("editTitle")}
      open={user !== null}
      isPending={isPending}
      submitText={t("editSubmit")}
      pendingText={t("editPending")}
      onClose={onClose}
      onSubmit={submitEdit}
    >
      <TextInput label={t("colUsername")} value={user?.username ?? ""} disabled />
      <TextInput
        label={t("colNickname")}
        value={nickname}
        error={nicknameError ?? fieldError("nickname")}
        required
        disabled={isPending}
        autoFocus
        onChange={setNickname}
      />
      {canAssignRole && (
        <SelectInput
          label={t("colRole")}
          value={selectedRoleId}
          error={fieldError("role_ids")}
          disabled={isPending}
          options={[{ value: "", label: t("roleUnassigned") }, ...roleOptions]}
          onChange={setSelectedRoleId}
        />
      )}
      {canToggleStatus && (
        <SelectInput
          label={t("colStatus")}
          value={isDisabled ? "disabled" : "active"}
          error={fieldError("is_disabled")}
          disabled={isPending}
          options={statusOptions}
          onChange={(value) => setIsDisabled(value === "disabled")}
        />
      )}
    </FormDialog>
  )
}
