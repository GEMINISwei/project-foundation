import { redirect } from "next/navigation"
import { getCurrentUser } from "@/modules/auth/public.server"
import { LOGIN_REDIRECT_REASONS, loginUrl } from "@/shared/session/login-contract"

/** 這一層底下都要登入。proxy.ts 只看有沒有 cookie, 憑證是否仍然有效在這裡向後端確認。 */
export default async function ProtectedLayout({ children }: React.PropsWithChildren) {
  if (!(await getCurrentUser())) {
    redirect(loginUrl(LOGIN_REDIRECT_REASONS.sessionExpired))
  }

  return children
}
