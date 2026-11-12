"use client"

import { useState } from "react"
import {
  Container,
  FilterDialog,
  ListPageHeader,
  Notify,
  useListFeedback,
  useStatusFilterOptions,
} from "@/shared/ui"
import type { PageMeta } from "@/shared/api/types"
import { useT } from "@/shared/i18n/context"
import { rolesMessages } from "../i18n"
import type { RoleFilters, RoleInfo } from "../types"
import CreateRoleDialog from "./CreateRoleDialog"
import EditRoleDialog from "./EditRoleDialog"
import RolesTable from "./RolesTable"

type Dialog = "create" | "edit" | null

type RolesViewProps = {
  roles: RoleInfo[]
  meta: PageMeta
  seq: number
  limit: number
  errorMessage: string
  canWrite: boolean
  filters: RoleFilters
}

export default function RolesView({
  roles,
  meta,
  seq,
  limit,
  errorMessage,
  canWrite,
  filters,
}: RolesViewProps) {
  const t = useT(rolesMessages)
  const statusFilterOptions = useStatusFilterOptions()
  const showReset = meta.prevCursor !== null
  const [dialog, setDialog] = useState<Dialog>(null)
  const [selectedRole, setSelectedRole] = useState<RoleInfo | null>(null)
  const [filterDialogOpen, setFilterDialogOpen] = useState(false)

  function closeDialog() {
    setDialog(null)
    setSelectedRole(null)
  }

  function openCreate() {
    setDialog("create")
  }

  function openEdit(role: RoleInfo) {
    setSelectedRole(role)
    setDialog("edit")
  }

  const { notify, closeNotify, handleSuccess, handleError } = useListFeedback(closeDialog)

  return (
    <Container size="lg" padded>
      <ListPageHeader
        title={t("heading")}
        subtitle={t("subtitle")}
        showReset={showReset}
        onFilter={() => setFilterDialogOpen(true)}
        createAction={canWrite ? { label: t("create"), onClick: openCreate } : undefined}
      />

      <RolesTable
        roles={roles}
        meta={meta}
        seq={seq}
        limit={limit}
        errorMessage={errorMessage}
        canWrite={canWrite}
        onEdit={openEdit}
      />

      <FilterDialog
        key={filterDialogOpen ? "filter-open" : "filter-closed"}
        title={t("filterTitle")}
        open={filterDialogOpen}
        onClose={() => setFilterDialogOpen(false)}
        fields={[
          { name: "name", label: t("colName"), type: "text" },
          {
            name: "is_disabled",
            label: t("colStatus"),
            type: "select",
            options: statusFilterOptions,
          },
        ]}
        initialValues={{ name: filters.name, is_disabled: filters.isDisabled }}
      />

      <CreateRoleDialog
        open={dialog === "create"}
        onClose={closeDialog}
        onSuccess={handleSuccess}
        onError={handleError}
      />
      <EditRoleDialog
        key={dialog === "edit" ? selectedRole?.id : "closed"}
        role={dialog === "edit" ? selectedRole : null}
        onClose={closeDialog}
        onSuccess={handleSuccess}
        onError={handleError}
      />

      <Notify {...notify} onOpenChange={(open) => { if (!open) closeNotify() }} />
    </Container>
  )
}
