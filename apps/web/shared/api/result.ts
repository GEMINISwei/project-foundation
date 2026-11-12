/** `ApiResult` 的讀取輔助。純函式, server 與 client 都能用。 */

import type { ApiResult } from "./types"

/** 失敗時要顯示的訊息; 後端沒給訊息 (連不上) 時用 `fallback`。附上 request id 方便回報。 */
export function errorMessage<T>(result: ApiResult<T>, fallback: string): string {
  if (result.ok) return ""
  const { message, requestId } = result.error
  const text = message || fallback
  return requestId ? `${text} (${requestId})` : text
}

export function fieldErrors<T>(result: ApiResult<T>): Record<string, string> {
  return result.ok ? {} : result.error.fields
}
