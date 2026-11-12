import { UsersPage, generateUsersMetadata, type UsersPageProps } from "@/modules/users/public.server"

export const generateMetadata = generateUsersMetadata

export default function Page(props: UsersPageProps) {
  return <UsersPage {...props} />
}
