"use client"

import { useState } from "react"
import { Container, ListPageHeader, Notify, useListFeedback } from "@/shared/ui"
import type { PageMeta } from "@/shared/api/types"
import { useT } from "@/shared/i18n/context"
// 角色顯示名稱的規則 (系統角色走字典) 由 roles 模組唯一擁有, 這裡經 public entry 取用。
import { getRoleDisplayName, rolesMessages } from "@/modules/roles/public.client"
import { usersMessages } from "../i18n"
import { isAssignableRole } from "../capabilities"
import type { RoleInfo, UserFilters, UserInfo } from "../types"
import CreateUserDialog from "./CreateUserDialog"
import EditUserDialog from "./EditUserDialog"
import ResetPasswordDialog from "./ResetPasswordDialog"
import UsersTable from "./UsersTable"
import UsersFilterDialog from "./UsersFilterDialog"

type Dialog = "create" | "edit" | "reset" | null

type UsersViewProps = {
  users: UserInfo[]
  meta: PageMeta
  seq: number
  limit: number
  currentUserId: string | undefined
  canWrite: boolean
  roles: RoleInfo[]
  errorMessage: string
  filters: UserFilters
}

export default function UsersView({
  users,
  meta,
  seq,
  limit,
  currentUserId,
  canWrite,
  roles,
  errorMessage,
  filters,
}: UsersViewProps) {
  const t = useT(usersMessages)
  const roleT = useT(rolesMessages)
  const showReset = meta.prevCursor !== null
  const [dialog, setDialog] = useState<Dialog>(null)
  const [selectedUser, setSelectedUser] = useState<UserInfo | null>(null)
  const [filterDialogOpen, setFilterDialogOpen] = useState(false)
  // 只有指派得出去的角色進得了這份清單; 篩選用的那份規則不同, 由 UsersFilterDialog 自己組。
  const roleOptions = roles.filter(isAssignableRole).map((role) => ({
    value: role.id,
    label: getRoleDisplayName(role, roleT),
  }))

  function closeSelectedDialog() {
    setDialog(null)
    setSelectedUser(null)
  }

  function openCreate() { setDialog("create") }

  function openFor(user: UserInfo, nextDialog: Exclude<Dialog, "create" | null>) {
    setSelectedUser(user)
    setDialog(nextDialog)
  }

  const { notify, closeNotify, handleSuccess, handleError } = useListFeedback(closeSelectedDialog)

  return (
    <Container size="lg" padded>
      <ListPageHeader
        title={t("heading")}
        subtitle={t("subtitle")}
        showReset={showReset}
        onFilter={() => setFilterDialogOpen(true)}
        createAction={canWrite ? { label: t("create"), onClick: openCreate } : undefined}
      />

      <UsersTable
        users={users}
        meta={meta}
        seq={seq}
        limit={limit}
        currentUserId={currentUserId}
        canWrite={canWrite}
        errorMessage={errorMessage}
        onEdit={(user) => openFor(user, "edit")}
        onResetPassword={(user) => openFor(user, "reset")}
      />

      <CreateUserDialog
        open={dialog === "create"}
        onClose={() => setDialog(null)}
        onSuccess={handleSuccess}
        onError={handleError}
        roleOptions={roleOptions}
      />
      <EditUserDialog
        key={dialog === "edit" ? selectedUser?.id : "closed"}
        user={dialog === "edit" ? selectedUser : null}
        onClose={closeSelectedDialog}
        onSuccess={handleSuccess}
        onError={handleError}
        currentUserId={currentUserId}
        roleOptions={roleOptions}
      />
      <ResetPasswordDialog
        user={dialog === "reset" ? selectedUser : null}
        onClose={closeSelectedDialog}
        onSuccess={handleSuccess}
        onError={handleError}
      />
      <UsersFilterDialog
        key={filterDialogOpen ? "filter-open" : "filter-closed"}
        open={filterDialogOpen}
        onClose={() => setFilterDialogOpen(false)}
        roles={roles}
        filters={filters}
      />

      <Notify {...notify} onOpenChange={(open) => { if (!open) closeNotify() }} />
    </Container>
  )
}
