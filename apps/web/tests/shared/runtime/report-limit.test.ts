import { expect, it } from "vitest"

import { createReportLimiter } from "@/shared/runtime/report-limit"

/**
 * 錯誤回報的入口不用登入: 沒有上限的話, 任何人都能把伺服器的 log 灌滿, 真正的錯誤紀錄會被擠掉。
 * 上限分兩層: 單一來源的, 以及換來源也繞不過的合計。
 */

const MINUTE = 60_000

it("同一個來源超過上限的回報會被丟掉", () => {
  const limiter = createReportLimiter()

  const results = Array.from({ length: 6 }, () => limiter.allow("203.0.113.7", 0))

  expect(results).toEqual([true, true, true, true, true, false])
  expect(limiter.allow("203.0.113.8", 0)).toBe(true)
})

it("所有來源合計超過上限時不再記錄", () => {
  const limiter = createReportLimiter()

  const results = Array.from({ length: 31 }, (_, index) => limiter.allow(`198.51.100.${index}`, 0))

  expect(results.filter(Boolean)).toHaveLength(30)
  expect(results.at(-1)).toBe(false)
})

it("時間窗過了之後重新開始計數", () => {
  const limiter = createReportLimiter()
  for (let count = 0; count < 6; count += 1) limiter.allow("203.0.113.7", 0)

  expect(limiter.allow("203.0.113.7", MINUTE - 1)).toBe(false)
  expect(limiter.allow("203.0.113.7", MINUTE)).toBe(true)
})
