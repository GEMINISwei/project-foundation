/**
 * 後端契約在前端的型別。全部從 `schema.d.ts` (由 contracts/openapi.json 產生) 衍生,
 * 後端改了欄位、權限或語系, 這裡用到的地方會編譯失敗。
 */

import type { components } from "./schema"

type Schemas = components["schemas"]

/** 以名稱取用後端的資料結構: `Schema<"RoleInfo">`。業務型別在各模組的 types.ts 命名。 */
export type Schema<Name extends keyof Schemas> = Schemas[Name]

export type Permission = Schemas["Permission"]
export type Language = Schemas["Language"]

export type ApiError = {
  status: number
  /** 固定的錯誤代碼 (`roles.name_exists`), 分支判斷用它, 不要比對訊息文字。 */
  code: string
  message: string
  /** 顯示在錯誤訊息旁, 使用者回報時可以用 `make logs trace <id>` 查。 */
  requestId: string
  /** 欄位名稱 → 訊息。 */
  fields: Record<string, string>
}

/** 每次呼叫後端的結果。Server Action 直接回傳它, 所以內容都要能序列化。 */
export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError }

export type PageMeta = {
  total: number
  nextCursor: string | null
  prevCursor: string | null
}

export const EMPTY_PAGE_META: PageMeta = { total: 0, nextCursor: null, prevCursor: null }
