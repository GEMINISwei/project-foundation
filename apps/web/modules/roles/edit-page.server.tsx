import "server-only"
import { redirect } from "next/navigation"
import { requirePermission } from "@/modules/auth/public.server"
import { hasPermission } from "@/shared/access/permissions"
import { api, call } from "@/shared/api/client.server"
import { getT } from "@/shared/i18n/locale.server"
import { rolesMessages } from "./i18n"
import { ROLES_PATH } from "./manifest"
import RoleEditView from "./ui/RoleEditView"

export type RoleEditPageProps = {
  params: Promise<{ id: string }>
}

export async function generateMetadata() {
  return { title: (await getT(rolesMessages))("managePermissions") }
}

export default async function RoleEditPage({ params }: RoleEditPageProps) {
  const { id } = await params
  const currentUser = await requirePermission("roles:read")
  const [role, options] = await Promise.all([
    call(api.GET("/api/roles/{role_id}", { params: { path: { role_id: id } } })),
    call(api.GET("/api/roles/permission-options")),
  ])
  if (!role.ok) redirect(ROLES_PATH)

  return (
    <RoleEditView
      role={role.data}
      permissionOptions={options.ok ? options.data.items : []}
      canWrite={hasPermission(currentUser?.permissions ?? [], "roles:write")}
    />
  )
}
