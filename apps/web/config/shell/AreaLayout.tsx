import { getCurrentUser } from "@/modules/auth/public.server"
import { hasAllPermission } from "@/shared/access/permissions"
import { getT } from "@/shared/i18n/locale.server"
import type { RouteArea } from "@/shared/module"
import { appMessages } from "@/config/i18n"
import AppShell from "./AppShell"
import styles from "./shell.module.css"

type AreaLayoutProps = {
  area: RouteArea
  children: React.ReactNode
}

/** 兩區共用的外殼。`<main>` 由這裡提供, 頁面與模組不自己渲染。 */
export default async function AreaLayout({ area, children }: AreaLayoutProps) {
  const t = await getT(appMessages)
  const user = await getCurrentUser()
  const permissions = user?.permissions ?? []

  return (
    <AppShell
      area={area}
      nickname={user?.nickname ?? ""}
      userRole={hasAllPermission(permissions) ? t("roleSuperAdmin") : t("roleUser")}
      permissions={permissions}
    >
      <main className={styles.main}>{children}</main>
    </AppShell>
  )
}
