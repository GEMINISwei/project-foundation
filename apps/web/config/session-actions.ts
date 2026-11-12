"use server"

import { redirect } from "next/navigation"
import { api, call } from "@/shared/api/client.server"
import { clearAccessTokenCookie } from "@/shared/session/access-token.server"
import { LOGIN_PATH } from "@/shared/session/login-contract"

export async function logout() {
  // 後端那一步失敗 (憑證已經失效、後端重啟中) 也要把 cookie 清掉並回到登入頁。
  await call(api.POST("/api/users/me/logout"), { auth: "none" })
  await clearAccessTokenCookie()
  redirect(LOGIN_PATH)
}
