"use client"

import { FilterDialog, useStatusFilterOptions } from "@/shared/ui"
import { useT } from "@/shared/i18n/context"
import { getRoleDisplayName, rolesMessages } from "@/modules/roles/public.client"
import { usersMessages } from "../i18n"
import type { RoleInfo, UserFilters } from "../types"

type UsersFilterDialogProps = {
  open: boolean
  onClose: () => void
  roles: RoleInfo[]
  filters: UserFilters
}

/**
 * 使用者列表的篩選對話框。
 *
 * 字典與狀態選項在這裡自己取, 不從 `UsersView` 傳進來: 那些是這個對話框自己的顯示細節,
 * 讓它們往上冒只會讓列表元件多背幾個跟列表無關的變數。
 */
export default function UsersFilterDialog({
  open,
  onClose,
  roles,
  filters,
}: UsersFilterDialogProps) {
  const t = useT(usersMessages)
  const roleT = useT(rolesMessages)
  const statusFilterOptions = useStatusFilterOptions()

  // 篩選是「找出有哪些人是這個角色」, 跟指派角色的用途不同,
  // 所以系統目前有的角色 (含超級管理者、已停用的角色) 都要能篩選。
  const roleOptions = roles.map((role) => ({
    value: role.id,
    label: role.is_disabled
      ? t("roleDisabledSuffix", { name: getRoleDisplayName(role, roleT) })
      : getRoleDisplayName(role, roleT),
  }))

  return (
    <FilterDialog
      title={t("filterTitle")}
      open={open}
      onClose={onClose}
      fields={[
        { name: "name", label: t("colName"), type: "text" },
        {
          name: "role_id",
          label: t("colRole"),
          type: "select",
          options: [
            { value: "", label: t("filterAll") },
            { value: "unassigned", label: t("roleUnassigned") },
            ...roleOptions,
          ],
        },
        {
          name: "is_disabled",
          label: t("colStatus"),
          type: "select",
          options: statusFilterOptions,
        },
      ]}
      initialValues={{
        name: filters.name,
        role_id: filters.roleId,
        is_disabled: filters.isDisabled,
      }}
    />
  )
}
