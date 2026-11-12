import { RoleEditPage, generateRoleEditMetadata, type RoleEditPageProps } from "@/modules/roles/public.server"

export const generateMetadata = generateRoleEditMetadata

export default function Page(props: RoleEditPageProps) {
  return <RoleEditPage {...props} />
}
