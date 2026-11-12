"use server"

import { type ActionFormData, getActionFormString } from "@/shared/api/action-form-data"
import { api, call } from "@/shared/api/client.server"
import { setAccessTokenCookie } from "@/shared/session/access-token.server"
import { withoutData } from "@/shared/session/token-response"
import type { LoginFormValues } from "./types"

// 參數用 FormData: 密碼不會以純物件的形式出現在 Server Action 的參數紀錄裡。
export async function loginUser(formData: ActionFormData<LoginFormValues>) {
  const result = await call(
    api.POST("/api/users/login", {
      body: {
        username: getActionFormString(formData, "username"),
        password: getActionFormString(formData, "password"),
      },
    }),
    { auth: "none" },
  )
  if (result.ok) await setAccessTokenCookie(result.data.access_token)
  return withoutData(result)
}
