"use server"

import { headers } from "next/headers"
import { logEvent } from "./log.server"
import { createReportLimiter, REPORT_WINDOW_MS } from "./report-limit"

const MAX_LENGTH = 2000
const limiter = createReportLimiter()
// 已經排好摘要的時間窗: 一個時間窗只排一次。
let summaryScheduledFor: number | null = null

/** 這個時間窗第一次丟掉回報時, 排一個在它結束時寫摘要的計時器: 一分鐘最多一行。 */
function scheduleDroppedSummary(now: number) {
  const start = limiter.windowStart()
  if (summaryScheduledFor === start) return
  summaryScheduledFor = start
  const timer = setTimeout(() => {
    const count = limiter.takeDropped(start)
    if (count > 0) logEvent("warning", "client_error_dropped", { count })
  }, start + REPORT_WINDOW_MS - now)
  // 不讓這個計時器擋住行程結束。
  timer.unref()
}

function clip(value: unknown): string {
  return typeof value === "string" ? value.slice(0, MAX_LENGTH) : ""
}

/**
 * 把瀏覽器端的錯誤記進伺服器的 log: 少了它, 使用者眼前的錯誤在主機上完全看不到。
 * 內容來自瀏覽器, 所以限制長度, 而且只當成文字記錄; 這個入口不用登入, 所以超過上限的直接丟掉,
 * 只在那一分鐘結束時留一行丟了幾筆。
 */
export async function reportClientError(report: { message: string; stack?: string; path: string }) {
  const headerStore = await headers()
  const now = Date.now()
  if (!limiter.allow(headerStore.get("x-real-ip") ?? "-", now)) {
    scheduleDroppedSummary(now)
    return
  }
  logEvent("error", "client_error", {
    request_id: headerStore.get("x-request-id") ?? "-",
    message: clip(report.message),
    stack: clip(report.stack),
    path: clip(report.path).split("?")[0],
    user_agent: clip(headerStore.get("user-agent")),
  })
}
