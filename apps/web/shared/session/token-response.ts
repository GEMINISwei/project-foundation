import type { ApiResult } from "@/shared/api/types"

/**
 * Server Action 的回傳值會送進瀏覽器。登入與換密碼的回應帶著登入憑證, 寫進 httpOnly cookie
 * 之後要用這個把內容拿掉再回傳, 憑證才不會出現在瀏覽器的 JavaScript 裡。
 */
export function withoutData<T>(result: ApiResult<T>): ApiResult<null> {
  return result.ok ? { ok: true, data: null } : result
}
