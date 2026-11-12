import "server-only"
import { getT } from "@/shared/i18n/locale.server"
import { authMessages } from "./i18n"
import LoginForm from "./ui/LoginForm"
import { getLoginRedirectReason } from "./validation"

// 標題跟著語系走, 所以是 generateMetadata 而不是靜態 metadata。
// route adapter 要轉出的名字也跟著改 (見 app/(public)/login/page.tsx)。
export async function generateMetadata() {
  return { title: (await getT(authMessages))("loginTitle") }
}

export type LoginPageProps = {
  searchParams?: Promise<{
    reason?: string | string[]
  }>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams

  return (
    <LoginForm reason={getLoginRedirectReason(params?.reason)} />
  )
}
