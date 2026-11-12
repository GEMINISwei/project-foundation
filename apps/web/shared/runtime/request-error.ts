/**
 * 伺服器端算繪或 Server Action 丟出未處理的錯誤時記一筆 (instrumentation.ts 的 onRequestError)。
 * 格式與 api 的 log 相同, 帶 request id 與 digest: 錯誤畫面上顯示的就是這個 digest。
 */

type ErrorRequest = {
  readonly path: string
  readonly method: string
  readonly headers: Readonly<Record<string, string | string[] | undefined>>
}

function headerValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function digestOf(error: unknown): string | undefined {
  if (typeof error !== "object" || error === null || !("digest" in error)) return undefined
  return typeof error.digest === "string" ? error.digest : undefined
}

export function formatRequestError(error: unknown, request: ErrorRequest, now = new Date()) {
  return JSON.stringify({
    event: "unhandled_error",
    level: "error",
    timestamp: now.toISOString(),
    request_id: headerValue(request.headers["x-request-id"]) ?? "-",
    digest: digestOf(error) ?? "-",
    method: request.method,
    // 不記 query string: 敏感內容會長期留在 log 裡。
    path: request.path.split("?")[0],
    error: String(error),
    stack: error instanceof Error ? error.stack : undefined,
  })
}
