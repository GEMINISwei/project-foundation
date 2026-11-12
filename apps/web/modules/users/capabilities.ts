/** 使用者管理畫面的分支規則。真正的授權在後端 (modules/users/service.py), 這裡只決定顯示什麼。 */

import type { Translator } from "@/shared/i18n/dictionary"
import { getRoleDisplayName, type rolesMessages } from "@/modules/roles/public.client"
import type { usersMessages } from "./i18n"
import type { RoleInfo, UserInfo } from "./types"

type UsersT = Translator<(typeof usersMessages)["zh"]>
type RolesT = Translator<(typeof rolesMessages)["zh"]>

const SUPER_ADMIN_CODE = "super_admin"

export function isSuperAdminUser(user: UserInfo) {
  return user.roles.some((role) => role.code === SUPER_ADMIN_CODE)
}

export function formatRoleNames(user: UserInfo, t: UsersT, roleT: RolesT): string {
  const names = user.roles.map((role) => {
    const name = getRoleDisplayName(role, roleT)
    return role.is_disabled ? t("roleDisabledSuffix", { name }) : name
  })
  return names.length > 0 ? names.join(t("roleSeparator")) : t("roleUnassigned")
}

/** 這一列可以做哪些操作。超級管理者的帳號後台完全不能動; 自己不能停用自己或改自己的角色。 */
export function getUserActions(
  user: UserInfo,
  currentUserId: string | undefined,
  canWrite: boolean,
  hasRoleOptions: boolean,
) {
  const manageable = canWrite && !isSuperAdminUser(user)
  const isSelf = user.id === currentUserId
  return {
    canEdit: manageable,
    canResetPassword: manageable,
    canAssignRole: manageable && !isSelf && hasRoleOptions,
    canToggleStatus: manageable && !isSelf,
  }
}

/**
 * 編輯送出的角色。畫面一次只能選一個角色: 選擇沒變時原樣送回 (帳號原本有多個角色時才不會被
 * 這個單選欄位悄悄清掉), 不能改角色時也一樣。
 */
export function roleIdsForUpdate(
  canAssignRole: boolean,
  selectedRoleId: string,
  originalRoleIds: string[],
): string[] {
  if (!canAssignRole || selectedRoleId === (originalRoleIds[0] ?? "")) return originalRoleIds
  return selectedRoleId ? [selectedRoleId] : []
}

export function isAssignableRole(role: RoleInfo) {
  return !role.is_disabled && role.code === null
}
