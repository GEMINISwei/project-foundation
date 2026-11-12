"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"
import { Button, Form, FormPageShell, Notify, useActionSubmit, useNotify } from "@/shared/ui"
import { useT } from "@/shared/i18n/context"
import { rolesMessages } from "../i18n"
import { getRoleDisplayName } from "../constants"
import { canManageRole } from "../capabilities"
import { updateRole } from "../actions"
import { ROLES_PATH } from "../manifest"
import type { AssignablePermission, PermissionOption, RoleInfo } from "../types"
import PermissionChecklist from "./PermissionChecklist"

type RoleEditViewProps = {
  role: RoleInfo
  permissionOptions: PermissionOption[]
  canWrite: boolean
}

export default function RoleEditView({ role, permissionOptions, canWrite }: RoleEditViewProps) {
  const t = useT(rolesMessages)
  const router = useRouter()
  const readOnly = !canWrite || !canManageRole(role)
  // 超級管理者角色存的是 `*`, 畫面上顯示成全部勾選。
  const initial = role.permissions.includes("*")
    ? permissionOptions.map((option) => option.value as AssignablePermission)
    : role.permissions.filter((item): item is AssignablePermission => item !== "*")
  const [permissions, setPermissions] = useState<AssignablePermission[]>(initial)
  const { isPending, submit, fieldError } = useActionSubmit()
  const { notify, notifyError, closeNotify } = useNotify()

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submit(
      () => updateRole(role.id, { name: role.name, permissions, is_disabled: role.is_disabled }),
      {
        onSuccess: () => router.push(ROLES_PATH),
        onError: notifyError,
        errorFallback: t("updateFailed"),
      },
    )
  }

  return (
    <FormPageShell
      title={t(readOnly ? "viewPermissions" : "managePermissions")}
      subtitle={getRoleDisplayName(role, t)}
      backHref={ROLES_PATH}
      backLabel={t("backToList")}
      actions={readOnly ? null : (
        <Button type="submit" disabled={isPending} form="role-edit-form">
          {isPending ? t("saving") : t("save")}
        </Button>
      )}
    >
      <Form id="role-edit-form" onSubmit={handleSubmit}>
        <PermissionChecklist
          permissionOptions={permissionOptions}
          selectedPermissions={permissions}
          disabled={readOnly || isPending}
          error={fieldError("permissions")}
          onChange={setPermissions}
        />
        <Notify {...notify} onOpenChange={(open) => { if (!open) closeNotify() }} />
      </Form>
    </FormPageShell>
  )
}
