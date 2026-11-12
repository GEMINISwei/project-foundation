// 設定頁的表單型別收在這裡 (同 modules/auth/types.ts: 模組的公開形狀由 public.server.ts
// 決定, 內部不分層)。

export type PasswordFormValues = {
  current_password: string
  new_password: string
  // 只存在於瀏覽器這一側 —— 後端不需要它, 所以 Server Action 收的是下面那個窄型別。
  confirm_password: string
}

export type PasswordFormErrors = Partial<Record<keyof PasswordFormValues, string>>

/** 真的會送到後端的欄位 (對應 `PATCH /users/me/password` 的 body)。 */
export type PasswordChangeRequest = Pick<PasswordFormValues, "current_password" | "new_password">

/** 對應 `PATCH /users/me` 的 body: 使用者能改的自己的資料。 */
export type ProfileUpdateRequest = { nickname: string }
