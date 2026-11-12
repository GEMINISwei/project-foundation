// 模組的公開形狀由 `public.server.ts` 決定, 內部型別收在這一個 `types.ts`, 不另外分層。

// 導向原因是 shared 與 auth 共用的約定, 定義在 shared (理由見那份檔案)。
export type { LoginRedirectReason } from "@/shared/session/login-contract"

export type LoginFormValues = {
  username: string
  password: string
}

export type LoginFormErrors = Partial<Record<keyof LoginFormValues, string>>
