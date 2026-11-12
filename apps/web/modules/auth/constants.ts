import type { LoginRedirectReason } from "./types"

// 導向原因 → 字典 key。訊息本體在 `./i18n.ts`, 這裡只留對應關係 ——
// 新增一種 reason 時, 少了對應 key 會編譯失敗。
export const LOGIN_REDIRECT_MESSAGE_KEYS = {
  "session-expired": "sessionExpired",
} as const satisfies Record<LoginRedirectReason, string>
