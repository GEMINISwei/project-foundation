/**
 * 錯誤回報的上限 (固定時間窗)。回報的入口不用登入, 沒有上限的話任何人都能把 log 灌滿,
 * 真正的錯誤紀錄會被擠掉。
 *
 * 分兩層: 單一來源的上限擋一個壞掉或惡意的瀏覽器; 合計的上限讓換來源也灌不爆。
 * 計數放在行程的記憶體裡: web 只有一個行程, 重啟歸零也無妨。
 *
 * 被丟掉的也要數: 不留痕跡的話, 看 log 的人不知道有東西被擋下。呼叫端在時間窗結束時用
 * `takeDropped()` 取出筆數, 寫成一行摘要。
 */

export const REPORT_WINDOW_MS = 60_000
const MAX_PER_SOURCE = 5
const MAX_TOTAL = 30

export function createReportLimiter() {
  let windowStart = 0
  let total = 0
  let dropped = 0
  // 上一個時間窗: 摘要是在時間窗結束之後才取的, 那時可能已經換到下一個了。
  let previous = { start: 0, dropped: 0 }
  const perSource = new Map<string, number>()

  return {
    /** 記一次回報; 超過上限時回傳 false, 呼叫端就不該再寫 log。 */
    allow(source: string, now: number): boolean {
      if (now - windowStart >= REPORT_WINDOW_MS) {
        previous = { start: windowStart, dropped }
        windowStart = now
        total = 0
        dropped = 0
        perSource.clear()
      }
      const count = perSource.get(source) ?? 0
      // 先看合計: 被擋下的來源不進 Map, 它的大小才不會超過合計的上限。
      if (total >= MAX_TOTAL || count >= MAX_PER_SOURCE) {
        dropped += 1
        return false
      }
      total += 1
      perSource.set(source, count + 1)
      return true
    },
    /** 目前這個時間窗的起點, 用來指名要取哪一個時間窗的筆數。 */
    windowStart(): number {
      return windowStart
    },
    /** 取出那個時間窗丟掉的筆數; 取過就歸零, 同一批不會被算兩次。 */
    takeDropped(start: number): number {
      if (start === windowStart) {
        const count = dropped
        dropped = 0
        return count
      }
      if (start !== previous.start) return 0
      const count = previous.dropped
      previous = { ...previous, dropped: 0 }
      return count
    },
  }
}
