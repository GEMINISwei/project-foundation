"use client"

import { useRouter } from "next/navigation"
import { Pencil, ShieldCheck } from "lucide-react"
import { ICON_SIZE } from "@/shared/ui"
import {
  ActionMenu,
  ErrorState,
  ListTableCard,
  Pagination,
  StatusBadge,
  Surface,
  TableRow,
} from "@/shared/ui"
import type { PageMeta } from "@/shared/api/types"
import { useT } from "@/shared/i18n/context"
import { rolesMessages } from "../i18n"
import { getRoleDisplayName } from "../constants"
import { canManageRole } from "../capabilities"
import { ROLES_PATH } from "../manifest"
import type { RoleInfo } from "../types"

type RolesTableProps = {
  roles: RoleInfo[]
  meta: PageMeta
  seq: number
  limit: number
  errorMessage: string
  canWrite: boolean
  onEdit: (role: RoleInfo) => void
}

/**
 * 角色列表本體 (錯誤狀態、表格、分頁)。
 *
 * 字典在這裡自己取, 不由 `RolesView` 傳進來。
 */
export default function RolesTable({
  roles,
  meta,
  seq,
  limit,
  errorMessage,
  canWrite,
  onEdit,
}: RolesTableProps) {
  const t = useT(rolesMessages)
  const router = useRouter()

  function getPermissionText(role: RoleInfo) {
    if (role.permissions.includes("*")) return t("allPermissions")
    return t("permissionCount", { count: role.permissions.length })
  }

  if (errorMessage) {
    return (
      <Surface>
        <ErrorState>{errorMessage}</ErrorState>
      </Surface>
    )
  }

  return (
    <>
      <ListTableCard
        headers={[t("colName"), t("colPermissions"), t("colStatus"), t("colActions")]}
        isEmpty={roles.length === 0}
        emptyText={t("empty")}
      >
        {roles.map((role) => (
          <TableRow key={role.id}>
            <td data-label={t("colName")}>{getRoleDisplayName(role, t)}</td>
            <td data-label={t("colPermissions")}>{getPermissionText(role)}</td>
            <td data-label={t("colStatus")}>
              <StatusBadge
                label={role.is_disabled ? t("statusDisabled") : t("statusActive")}
                variant={role.is_disabled ? "muted" : "success"}
              />
            </td>
            <td data-label={t("colActions")}>
              <ActionMenu
                items={[
                  // 系統角色的名稱、狀態與權限由初始資料擁有 (每次部署都會同步回去)。
                  canWrite && canManageRole(role) && {
                    icon: <Pencil size={ICON_SIZE.sm} />,
                    label: t("edit"),
                    onClick: () => onEdit(role),
                  },
                  (!canWrite || canManageRole(role)) && {
                    icon: <ShieldCheck size={ICON_SIZE.sm} />,
                    label: t(canWrite ? "managePermissions" : "viewPermissions"),
                    onClick: () => router.push(`${ROLES_PATH}/${role.id}/edit`),
                  },
                ]}
              />
            </td>
          </TableRow>
        ))}
      </ListTableCard>
      <Pagination
        meta={meta}
        seq={seq}
        limit={limit}
        summary={t("summary", { count: meta.total })}
      />
    </>
  )
}
