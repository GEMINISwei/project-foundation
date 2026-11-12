import { RolesPage, generateRolesMetadata, type RolesPageProps } from "@/modules/roles/public.server"

export const generateMetadata = generateRolesMetadata

export default function Page(props: RolesPageProps) {
  return <RolesPage {...props} />
}
