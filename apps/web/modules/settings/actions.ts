"use server"

import { type ActionFormData, getActionFormString } from "@/shared/api/action-form-data"
import { api, call } from "@/shared/api/client.server"
import { setAccessTokenCookie } from "@/shared/session/access-token.server"
import { withoutData } from "@/shared/session/token-response"
import type { PasswordChangeRequest, ProfileUpdateRequest } from "./types"

export async function changeOwnPassword(formData: ActionFormData<PasswordChangeRequest>) {
  const result = await call(
    api.PUT("/api/users/me/password", {
      body: {
        current_password: getActionFormString(formData, "current_password"),
        new_password: getActionFormString(formData, "new_password"),
      },
    }),
  )
  // 換密碼會讓所有既有的登入失效, 包含這一張: 要改用後端回傳的新憑證。
  if (result.ok) await setAccessTokenCookie(result.data.access_token)
  return withoutData(result)
}

export async function updateOwnProfile(formData: ActionFormData<ProfileUpdateRequest>) {
  return call(
    api.PATCH("/api/users/me", { body: { nickname: getActionFormString(formData, "nickname") } }),
  )
}
