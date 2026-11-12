"use server"

import {
  type ActionFormData,
  getActionFormString,
  getActionFormStrings,
} from "@/shared/api/action-form-data"
import { api, call } from "@/shared/api/client.server"
import { USERS_PATH } from "./manifest"
import type { CreateUserFormValues, ResetPasswordFormValues, UserUpdate } from "./types"

const refresh = { revalidate: USERS_PATH }

// 帶密碼的動作用 FormData 當參數: 密碼不會以純物件的形式出現在 Server Action 的參數紀錄裡。
export async function createUser(formData: ActionFormData<CreateUserFormValues>) {
  return call(
    api.POST("/api/users", {
      body: {
        username: getActionFormString(formData, "username"),
        nickname: getActionFormString(formData, "nickname"),
        password: getActionFormString(formData, "password"),
        role_ids: getActionFormStrings(formData, "role_ids"),
      },
    }),
    refresh,
  )
}

export async function updateUser(id: string, data: UserUpdate) {
  return call(
    api.PUT("/api/users/{user_id}", { params: { path: { user_id: id } }, body: data }),
    refresh,
  )
}

export async function resetUserPassword(formData: ActionFormData<ResetPasswordFormValues>) {
  return call(
    api.PUT("/api/users/{user_id}/password", {
      params: { path: { user_id: getActionFormString(formData, "id") } },
      body: { password: getActionFormString(formData, "password") },
    }),
  )
}
