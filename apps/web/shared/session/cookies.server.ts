// 不要在這個檔案加 "use server": 這是泛用的 cookie 寫入, 變成公開端點就能被拿來寫任意 cookie。
import "server-only"
import { cookies } from "next/headers"

type CookieOptions = {
  httpOnly: boolean
  secure: boolean
  sameSite: "lax" | "strict"
  path: string
  maxAge?: number
}

export async function createCookies(key: string, value: string, options: CookieOptions) {
  const cookieStore = await cookies()
  cookieStore.set(key, value, options)
}

export async function deleteCookies(key: string) {
  const cookieStore = await cookies()
  cookieStore.delete(key)
}
