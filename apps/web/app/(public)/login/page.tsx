import { LoginPage, generateLoginMetadata, type LoginPageProps } from "@/modules/auth/public.server"

export const generateMetadata = generateLoginMetadata

export default function Page(props: LoginPageProps) {
  return <LoginPage {...props} />
}
