import "server-only"
import { requirePermission } from "@/modules/auth/public.server"
import { getRoleOptions } from "@/modules/roles/public.server"
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
import { usersMessages } from "./i18n"
import UsersView from "./ui/UsersView"

export async function generateMetadata() {
  return { title: (await getT(usersMessages))("pageTitle") }
}

const USERS_PAGE_LIMIT = 10
/** 角色篩選的特殊值: 只列出沒有任何角色的帳號。與 UsersFilterDialog 的選項一致。 */
const UNASSIGNED = "unassigned"

export type UsersPageProps = {
  searchParams?: Promise<{
    cursor?: string
    direction?: string
    seq?: string
    name?: string
    role_id?: string
    is_disabled?: string
  }>
}

export default async function UsersPage({ searchParams }: UsersPageProps) {
  const t = await getT(usersMessages)
  const params = await searchParams
  const pagination = parsePagination(params)
  const name = params?.name ?? ""
  const roleId = params?.role_id ?? ""
  const isDisabled = parseBooleanFilter(params?.is_disabled)

  const currentUser = await requirePermission("users:read")
  const permissions = currentUser?.permissions ?? []
  const [result, roles] = await Promise.all([
    call(api.GET("/api/users", {
      params: {
        query: {
          ...pageQuery(pagination, USERS_PAGE_LIMIT),
          ...(name ? { keyword: name } : {}),
          ...(roleId === UNASSIGNED ? { unassigned: true } : roleId ? { role_id: roleId } : {}),
          is_disabled: toBoolean(isDisabled),
        },
      },
    })),
    // 只能查看使用者的人不一定看得到角色清單; 沒有清單時畫面就不提供角色篩選與指派。
    hasPermission(permissions, "roles:read") ? getRoleOptions() : [],
  ])
  const { items, meta, errorMessage } = pageFrom(result, t("listFailed"))

  return (
    <UsersView
      users={items}
      meta={meta}
      seq={pagination.seq}
      limit={USERS_PAGE_LIMIT}
      currentUserId={currentUser?.id}
      canWrite={hasPermission(permissions, "users:write")}
      roles={roles}
      errorMessage={errorMessage}
      filters={{ name, roleId, isDisabled }}
    />
  )
}
