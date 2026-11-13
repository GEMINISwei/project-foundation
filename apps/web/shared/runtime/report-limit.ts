/**
 * 錯誤回報的上限 (固定時間窗)。回報的入口不用登入, 沒有上限的話任何人都能把 log 灌滿,
 * 真正的錯誤紀錄會被擠掉。
 *
 * 分兩層: 單一來源的上限擋一個壞掉或惡意的瀏覽器; 合計的上限讓換來源也灌不爆。
 * 計數放在行程的記憶體裡: web 只有一個行程, 重啟歸零也無妨。
 */

const WINDOW_MS = 60_000
const MAX_PER_SOURCE = 5
const MAX_TOTAL = 30

export function createReportLimiter() {
  let windowStart = 0
  let total = 0
  const perSource = new Map<string, number>()

  return {
    /** 記一次回報; 超過上限時回傳 false, 呼叫端就不該再寫 log。 */
    allow(source: string, now: number): boolean {
      if (now - windowStart >= WINDOW_MS) {
        windowStart = now
        total = 0
        perSource.clear()
      }
      const count = perSource.get(source) ?? 0
      // 先看合計: 被擋下的來源不進 Map, 它的大小才不會超過合計的上限。
      if (total >= MAX_TOTAL || count >= MAX_PER_SOURCE) return false
      total += 1
      perSource.set(source, count + 1)
      return true
    },
  }
}
