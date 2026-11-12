import { redirect } from "next/navigation"
import { getCurrentUser } from "@/modules/auth/public.server"
import { accessibleRoutes } from "@/config/routes"
import AreaLayout from "@/config/shell/AreaLayout"

/** 後台: 至少進得去一個後台頁面才能進來。個別頁面的權限由後端的 API 把關。 */
export default async function AdminLayout({ children }: React.PropsWithChildren) {
  const user = await getCurrentUser()
  if (accessibleRoutes("admin", user?.permissions ?? []).length === 0) {
    redirect("/")
  }

  return <AreaLayout area="admin">{children}</AreaLayout>
}
