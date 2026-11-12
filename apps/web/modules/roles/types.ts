import type { Permission, Schema } from "@/shared/api/types"

export type RoleInfo = Schema<"RoleInfo">
export type RoleUpdate = Schema<"RoleUpdate">
export type PermissionOption = Schema<"PermissionOption">
/** 可以指派給一般角色的權限 (不含超級管理者的 `*`)。 */
export type AssignablePermission = Exclude<Permission, "*">

export type RoleFilters = {
  name: string
  isDisabled: string
}
