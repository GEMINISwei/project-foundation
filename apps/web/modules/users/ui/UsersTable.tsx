"use client"

import { KeyRound, Pencil } from "lucide-react"
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
import type { Translator } from "@/shared/i18n/dictionary"
import { rolesMessages } from "@/modules/roles/public.client"
import { usersMessages } from "../i18n"
import { formatRoleNames, getUserActions } from "../capabilities"
import type { UserInfo } from "../types"

type UsersT = Translator<(typeof usersMessages)["zh"]>

type UserRowProps = {
  user: UserInfo
  roleNames: string
  isSelf: boolean
  t: UsersT
  onEdit?: () => void
  /** 沒給就不顯示「重設密碼」(超級管理者帳號)。 */
  onResetPassword?: () => void
}

function UserRow({
  user,
  roleNames,
  isSelf,
  t,
  onEdit,
  onResetPassword,
}: UserRowProps) {
  return (
    <TableRow>
      <td data-label={t("colNickname")}>{user.nickname}{isSelf ? t("self") : ""}</td>
      <td data-label={t("colRole")}>{roleNames}</td>
      <td data-label={t("colStatus")}>
        <StatusBadge
          label={user.is_disabled ? t("statusDisabled") : t("statusActive")}
          variant={user.is_disabled ? "muted" : "success"}
        />
      </td>
      <td data-label={t("colActions")}>
        <ActionMenu
          items={[
            onEdit && { icon: <Pencil size={ICON_SIZE.sm} />, label: t("edit"), onClick: onEdit },
            onResetPassword && {
              icon: <KeyRound size={ICON_SIZE.sm} />,
              label: t("resetPassword"),
              onClick: onResetPassword,
            },
          ]}
        />
      </td>
    </TableRow>
  )
}

type UsersTableProps = {
  users: UserInfo[]
  meta: PageMeta
  seq: number
  limit: number
  currentUserId: string | undefined
  canWrite: boolean
  errorMessage: string
  onEdit: (user: UserInfo) => void
  onResetPassword: (user: UserInfo) => void
}

/**
 * 使用者列表本體 (錯誤狀態、表格、分頁)。
 *
 * 字典在這裡自己取, 不由 `UsersView` 傳進來。
 */
export default function UsersTable({
  users,
  meta,
  seq,
  limit,
  currentUserId,
  canWrite,
  errorMessage,
  onEdit,
  onResetPassword,
}: UsersTableProps) {
  const t = useT(usersMessages)
  const roleT = useT(rolesMessages)

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
        headers={[t("colNickname"), t("colRole"), t("colStatus"), t("colActions")]}
        isEmpty={users.length === 0}
        emptyText={t("empty")}
      >
        {users.map((user) => {
          const isSelf = user.id === currentUserId
          const actions = getUserActions(user, currentUserId, canWrite, true)

          return (
            <UserRow
              key={user.id}
              user={user}
              roleNames={formatRoleNames(user, t, roleT)}
              isSelf={isSelf}
              t={t}
              onEdit={actions.canEdit ? () => onEdit(user) : undefined}
              onResetPassword={
                actions.canResetPassword ? () => onResetPassword(user) : undefined
              }
            />
          )
        })}
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
