import type { Schema } from "@/shared/api/types"

export type UserInfo = Schema<"UserInfo">
export type UserUpdate = Schema<"UserUpdate">
export type RoleInfo = Schema<"RoleInfo">

export type UserFilters = {
  name: string
  roleId: string
  isDisabled: string
}

export type CreateUserFormValues = {
  username: string
  nickname: string
  password: string
  role_ids: string[]
}

export type ResetPasswordFormValues = {
  id: string
  password: string
}
