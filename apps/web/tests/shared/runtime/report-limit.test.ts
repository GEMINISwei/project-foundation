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

/**
 * 被丟掉的回報不留痕跡的話, 看 log 的人不知道有東西被擋下, 也看不出是不是有人在灌。
 * 所以每個時間窗丟了幾筆要取得到, 由呼叫端在時間窗結束時寫成一行摘要。
 */

it("被丟掉的回報會計數，時間窗結束後可以取得筆數", () => {
  const limiter = createReportLimiter()
  for (let count = 0; count < 8; count += 1) limiter.allow("203.0.113.7", 0)

  expect(limiter.takeDropped(limiter.windowStart())).toBe(3)
})

it("沒有丟掉任何回報時筆數是零，取過之後不重複計算", () => {
  const limiter = createReportLimiter()
  limiter.allow("203.0.113.7", 0)
  expect(limiter.takeDropped(limiter.windowStart())).toBe(0)

  for (let count = 0; count < 6; count += 1) limiter.allow("203.0.113.7", 0)
  expect(limiter.takeDropped(limiter.windowStart())).toBe(2)
  expect(limiter.takeDropped(limiter.windowStart())).toBe(0)
})

it("換到下一個時間窗之後，仍然取得到上一個時間窗丟掉的筆數", () => {
  const limiter = createReportLimiter()
  for (let count = 0; count < 7; count += 1) limiter.allow("203.0.113.7", 1000)
  const firstWindow = limiter.windowStart()

  // 摘要是用計時器在時間窗結束時寫的: 在那之前剛好有新的回報進來, 計數不能跟著被清掉。
  limiter.allow("203.0.113.7", 1000 + MINUTE)

  expect(limiter.windowStart()).toBe(1000 + MINUTE)
  expect(limiter.takeDropped(firstWindow)).toBe(2)
  expect(limiter.takeDropped(limiter.windowStart())).toBe(0)
})
