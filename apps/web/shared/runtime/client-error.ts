"use server"

import { headers } from "next/headers"
import { logEvent } from "./log.server"

const MAX_LENGTH = 2000

function clip(value: unknown): string {
  return typeof value === "string" ? value.slice(0, MAX_LENGTH) : ""
}

/**
 * 把瀏覽器端的錯誤記進伺服器的 log: 少了它, 使用者眼前的錯誤在主機上完全看不到。
 * 內容來自瀏覽器, 所以限制長度, 而且只當成文字記錄。
 */
export async function reportClientError(report: { message: string; stack?: string; path: string }) {
  const headerStore = await headers()
  logEvent("error", "client_error", {
    request_id: headerStore.get("x-request-id") ?? "-",
    message: clip(report.message),
    stack: clip(report.stack),
    path: clip(report.path).split("?")[0],
    user_agent: clip(headerStore.get("user-agent")),
  })
}
