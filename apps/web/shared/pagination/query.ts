/** 列表頁的分頁參數與回應整理。純函式。 */

import type { ApiResult, PageMeta } from "@/shared/api/types"
import { EMPTY_PAGE_META } from "@/shared/api/types"
import { errorMessage } from "@/shared/api/result"

export type PaginationSearchParams = {
  cursor?: string
  direction?: string
  seq?: string
}

export type ParsedPagination = {
  cursor: string | undefined
  direction: "next" | "prev"
  /** 目前是第幾頁。游標分頁沒有頁碼, 這個數字只跟著網址走, 給畫面顯示用。 */
  seq: number
}

export function parsePagination(params?: PaginationSearchParams): ParsedPagination {
  const seq = Number(params?.seq)

  return {
    cursor: params?.cursor,
    direction: params?.direction === "prev" ? "prev" : "next",
    seq: Number.isInteger(seq) && seq > 0 ? seq : 1,
  }
}

/** 送給後端列表端點的分頁參數。 */
export function pageQuery(parsed: ParsedPagination, limit: number) {
  return {
    limit,
    direction: parsed.direction,
    ...(parsed.cursor ? { cursor: parsed.cursor } : {}),
  }
}

type PageBody<T> = {
  items: T[]
  total: number
  next_cursor: string | null
  prev_cursor: string | null
}

/** 把列表端點的結果整理成畫面要的三樣東西; 失敗時是空列表加錯誤訊息。 */
export function pageFrom<T>(result: ApiResult<PageBody<T>>, fallback: string) {
  if (!result.ok) {
    return { items: [] as T[], meta: EMPTY_PAGE_META, errorMessage: errorMessage(result, fallback) }
  }
  const meta: PageMeta = {
    total: result.data.total,
    nextCursor: result.data.next_cursor,
    prevCursor: result.data.prev_cursor,
  }
  return { items: result.data.items, meta, errorMessage: "" }
}

/** 布林篩選只接受 "true"／"false", 其他值視為沒有篩選。 */
export function parseBooleanFilter(value?: string): "true" | "false" | "" {
  return value === "true" || value === "false" ? value : ""
}

export function toBoolean(value: "true" | "false" | ""): boolean | undefined {
  return value === "" ? undefined : value === "true"
}
