import "server-only"
import { requirePermission } from "@/modules/auth/public.server"
import { hasPermission } from "@/shared/access/permissions"
import { api, call } from "@/shared/api/client.server"
import { getT } from "@/shared/i18n/locale.server"
import {
  pageFrom,
  pageQuery,
  parseBooleanFilter,
  parsePagination,
  toBoolean,
} from "@/shared/pagination/query"
import { rolesMessages } from "./i18n"
import RolesView from "./ui/RolesView"

export async function generateMetadata() {
  return { title: (await getT(rolesMessages))("pageTitle") }
}

const ROLES_PAGE_LIMIT = 10

export type RolesPageProps = {
  searchParams?: Promise<{
    cursor?: string
    direction?: string
    seq?: string
    name?: string
    is_disabled?: string
  }>
}

export default async function RolesPage({ searchParams }: RolesPageProps) {
  const t = await getT(rolesMessages)
  const params = await searchParams
  const pagination = parsePagination(params)
  const name = params?.name ?? ""
  const isDisabled = parseBooleanFilter(params?.is_disabled)

  const currentUser = await requirePermission("roles:read")
  const result = await call(
    api.GET("/api/roles", {
      params: {
        query: {
          ...pageQuery(pagination, ROLES_PAGE_LIMIT),
          ...(name ? { name } : {}),
          is_disabled: toBoolean(isDisabled),
        },
      },
    }),
  )
  const { items, meta, errorMessage } = pageFrom(result, t("listFailed"))

  return (
    <RolesView
      roles={items}
      meta={meta}
      seq={pagination.seq}
      limit={ROLES_PAGE_LIMIT}
      errorMessage={errorMessage}
      canWrite={hasPermission(currentUser?.permissions ?? [], "roles:write")}
      filters={{ name, isDisabled }}
    />
  )
}
