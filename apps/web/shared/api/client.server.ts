// 不要在這個檔案加 "use server": 這裡的函式會變成任何人都能呼叫的端點, 拿來打任意後端路徑。
// 要開放寫入請在各模組的 actions.ts 包一層具名、窄介面的 Server Action。
import "server-only"

import { revalidatePath } from "next/cache"
import { cookies, headers } from "next/headers"
import { redirect } from "next/navigation"
import createClient, { type Middleware } from "openapi-fetch"
import { getLocale } from "@/shared/i18n/locale.server"
import { logEvent } from "@/shared/runtime/log.server"
import { clearAccessTokenCookie } from "@/shared/session/access-token.server"
import {
  ACCESS_TOKEN_COOKIE,
  LOGIN_REDIRECT_REASONS,
  loginUrl,
} from "@/shared/session/login-contract"
import type { paths } from "./schema"
import type { ApiError, ApiResult, Schema } from "./types"

const REQUEST_ID_HEADER = "x-request-id"

/** 每個請求帶上這次頁面請求的情境: 語系、登入憑證、追蹤 id 與用戶端 IP。 */
const withRequestContext: Middleware = {
  async onRequest({ request }) {
    const [cookieStore, headerStore, locale] = await Promise.all([
      cookies(),
      headers(),
      getLocale(),
    ])
    request.headers.set("Accept-Language", locale)
    const token = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value
    if (token) request.headers.set("Authorization", `Bearer ${token}`)
    // 沿用 nginx 產生的 id, 三層的 log 才串得起來。
    const requestId = headerStore.get(REQUEST_ID_HEADER)
    if (requestId) request.headers.set("X-Request-ID", requestId)
    // 後端的限流以它為 key。不要改讀 X-Forwarded-For: 那可以由用戶端偽造。
    const clientIp = headerStore.get("x-real-ip")
    if (clientIp) request.headers.set("X-Real-IP", clientIp)
    return request
  },
}

/**
 * 型別化的後端用戶端, 路徑、參數與回應型別都來自契約:
 *
 *     const result = await call(api.GET("/api/roles/{role_id}", { params: { path: { role_id } } }))
 */
export const api = createClient<paths>({
  // 走 compose 內網; 不要搬進 next.config 的 env, 那會把內部位址內嵌進 client bundle。
  baseUrl: process.env.API_URL || "http://api:8000",
  cache: "no-store",
  // 每次呼叫時才取用全域的 fetch (Next 會包裝它), 不在建立用戶端的當下就固定下來。
  fetch: (request) => fetch(request),
})
api.use(withRequestContext)

type FetchResult<T> = { data?: T; error?: unknown; response: Response }

type CallOptions = {
  /** `none`: 回 401 時不導向登入頁 (登入本身)。 */
  auth?: "required" | "none"
  /** 成功後要重新整理的頁面路徑。 */
  revalidate?: string
}

function toApiError(status: number, body: unknown, requestId: string): ApiError {
  const error = (typeof body === "object" && body !== null ? body : {}) as Partial<
    Schema<"ErrorBody">
  >
  return {
    status,
    code: error.code ?? "unknown",
    message: error.message ?? "",
    requestId: error.request_id ?? requestId,
    fields: Object.fromEntries((error.fields ?? []).map((item) => [item.field, item.message])),
  }
}

async function redirectToLogin(): Promise<never> {
  try {
    await clearAccessTokenCookie()
  } catch {
    // Server Component 的算繪階段不能寫 cookie; 刪不掉也要繼續導向, 否則會停在永遠 401 的頁面。
  }
  redirect(loginUrl(LOGIN_REDIRECT_REASONS.sessionExpired))
}

/** 執行一次後端呼叫, 把結果整理成 `ApiResult`。登入失效時導向登入頁。 */
export async function call<T>(
  request: Promise<FetchResult<T>>,
  options: CallOptions = {},
): Promise<ApiResult<T>> {
  const requestId = (await headers()).get(REQUEST_ID_HEADER) ?? ""
  let result: FetchResult<T>
  try {
    result = await request
  } catch (cause) {
    // 連不上後端 (重啟中、網路): 記下來, 畫面顯示呼叫端給的預設訊息。
    logEvent("error", "api_unreachable", { request_id: requestId, error: String(cause) })
    return { ok: false, error: toApiError(503, { code: "network" }, requestId) }
  }
  const { response } = result
  if (response.ok) {
    if (options.revalidate) revalidatePath(options.revalidate)
    return { ok: true, data: result.data as T }
  }
  if (response.status === 401 && options.auth !== "none") await redirectToLogin()
  return { ok: false, error: toApiError(response.status, result.error, requestId) }
}
