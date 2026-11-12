import { describe, expect, it } from "vitest"
import type { ApiResult } from "@/shared/api/types"
import {
  pageFrom,
  pageQuery,
  parseBooleanFilter,
  parsePagination,
  toBoolean,
} from "@/shared/pagination/query"

describe("parsePagination", () => {
  it("沒有參數時退回第一頁、往後翻", () => {
    expect(parsePagination()).toEqual({ cursor: undefined, direction: "next", seq: 1 })
  })

  it("只有 direction=prev 會被當成往前翻，其他值一律視為 next", () => {
    expect(parsePagination({ direction: "prev" }).direction).toBe("prev")
    expect(parsePagination({ direction: "next" }).direction).toBe("next")
    expect(parsePagination({ direction: "PREV" }).direction).toBe("next")
    expect(parsePagination({ direction: "亂填" }).direction).toBe("next")
  })

  it("seq 只接受正整數，其餘一律退回 1", () => {
    // seq 只用來顯示頁碼, 被亂填時不該讓畫面出現 NaN 或負數頁。
    expect(parsePagination({ seq: "3" }).seq).toBe(3)
    expect(parsePagination({ seq: "0" }).seq).toBe(1)
    expect(parsePagination({ seq: "-2" }).seq).toBe(1)
    expect(parsePagination({ seq: "abc" }).seq).toBe(1)
    expect(parsePagination({ seq: "" }).seq).toBe(1)
  })

  it("cursor 原樣傳遞（它對前端是不透明字串）", () => {
    expect(parsePagination({ cursor: "WyIyMDI2Il0=" }).cursor).toBe("WyIyMDI2Il0=")
  })
})

describe("parseBooleanFilter", () => {
  it("只接受 API 支援的布林字串", () => {
    expect(parseBooleanFilter("true")).toBe("true")
    expect(parseBooleanFilter("false")).toBe("false")
    expect(parseBooleanFilter("TRUE")).toBe("")
    expect(parseBooleanFilter("1")).toBe("")
    expect(parseBooleanFilter()).toBe("")
  })
})

describe("toBoolean", () => {
  it("空字串代表沒有篩選", () => {
    expect([toBoolean("true"), toBoolean("false"), toBoolean("")]).toEqual([true, false, undefined])
  })
})

describe("pageQuery", () => {
  it("沒有游標時不送 cursor 參數", () => {
    expect(pageQuery(parsePagination(), 10)).toEqual({ limit: 10, direction: "next" })
    expect(pageQuery(parsePagination({ cursor: "abc", direction: "prev" }), 10)).toEqual({
      limit: 10, direction: "prev", cursor: "abc",
    })
  })
})

describe("pageFrom", () => {
  type Body = {
    items: string[]
    total: number
    next_cursor: string | null
    prev_cursor: string | null
  }

  it("成功時整理出列表與分頁資訊", () => {
    const result: ApiResult<Body> = {
      ok: true,
      data: { items: ["a"], total: 5, next_cursor: "N", prev_cursor: null },
    }

    expect(pageFrom(result, "載入失敗")).toEqual({
      items: ["a"],
      meta: { total: 5, nextCursor: "N", prevCursor: null },
      errorMessage: "",
    })
  })

  it("失敗時是空列表加錯誤訊息，畫面不會壞掉", () => {
    const result: ApiResult<Body> = {
      ok: false,
      error: { status: 503, code: "network", message: "", requestId: "", fields: {} },
    }

    expect(pageFrom(result, "載入失敗")).toEqual({
      items: [],
      meta: { total: 0, nextCursor: null, prevCursor: null },
      errorMessage: "載入失敗",
    })
  })
})
