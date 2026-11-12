import type { Instrumentation } from "next"

/**
 * Next 的啟動掛勾。擋「image 裡的值」與「執行期給的值」對不起來的事 —— 那是**沒有症狀**的
 * 失敗, 所以要在開機當下就吵。
 */
export async function register() {
  // 動態 import 包在這個判斷裡: Next 才不會把 Node 專用的 API 編進 Edge 版本, build 與每個請求都報警告。
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { requireActionsEncryptionKey } = await import("@/shared/runtime/actions-key")
    requireActionsEncryptionKey()
  }
}

/**
 * 伺服器端的錯誤 (Server Component、Server Action、route handler) 印成一行帶 request id 與 digest 的紀錄,
 * 才對得上 nginx、api 的紀錄與使用者回報的錯誤代碼。動態 import 的理由同 `register`。
 */
export const onRequestError: Instrumentation.onRequestError = async (error, request) => {
  const { formatRequestError } = await import("@/shared/runtime/request-error")
  console.error(formatRequestError(error, request))
}
