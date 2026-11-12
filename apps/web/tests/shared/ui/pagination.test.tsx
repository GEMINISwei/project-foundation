/**
 * 分頁列的**網址組裝**。
 *
 * 為什麼值得測: 這一層是純字串運算, 但錯了會以「換頁之後篩選條件不見了」或
 * 「上一頁跳回第一頁」的形式出現 —— 使用者感覺得到, 型別檢查與 API 測試都看不到,
 * 因為送出去的請求本身完全合法, 只是參數少了幾個。
 *
 * 停用態同理: `hasPrevious` 是 true 但 `prevCursor` 是 null 時 (後端回應的正常狀態),
 * 必須渲染成不可點的 `aria-disabled`, 而不是一個指向 `cursor=null` 的連結。
 */

import { render, renderHook, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { PageMeta } from "@/shared/api/types"
import { Pagination, usePaginationResetHref } from "@/shared/ui"

// 每個 case 各自決定當下的網址。mock 讀的是這兩個變數, 所以要在 render 之前設好。
let pathname = "/records"
let search = ""

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(search),
}))

const meta = (overrides: Partial<PageMeta> = {}): PageMeta => ({
  nextCursor: null,
  prevCursor: null,
  total: 0,
  ...overrides,
})

describe("usePaginationResetHref", () => {
  it("只清掉游標參數，其他篩選條件留著", () => {
    // 「重置到第一頁」不等於「清空篩選」。少了這個區分, 使用者改一個篩選條件就會
    // 連同前面設好的其他條件一起被清掉。
    pathname = "/records"
    search = "cursor=abc&direction=next&seq=3&status=active&keyword=x"

    const { result } = renderHook(() => usePaginationResetHref())

    expect(result.current).toBe("/records?status=active&keyword=x")
  })

  it("沒有其他參數時只回路徑，不留下一個孤單的問號", () => {
    pathname = "/records"
    search = "cursor=abc&seq=2"

    const { result } = renderHook(() => usePaginationResetHref())

    expect(result.current).toBe("/records")
  })
})

describe("Pagination", () => {
  it("有下一頁時，連結帶著游標與 seq+1，並保留既有篩選", () => {
    pathname = "/records"
    search = "status=active"

    render(<Pagination meta={meta({ nextCursor: "NEXT" })} seq={3} limit={20} />)

    const href = screen.getByRole("link", { name: /下一頁/ }).getAttribute("href")
    const params = new URLSearchParams(href!.split("?")[1])
    expect(params.get("status")).toBe("active")
    expect(params.get("cursor")).toBe("NEXT")
    expect(params.get("direction")).toBe("next")
    expect(params.get("seq")).toBe("4")
  })

  it("上一頁的 seq 是往回一頁", () => {
    pathname = "/records"
    search = ""

    render(<Pagination meta={meta({ prevCursor: "PREV" })} seq={3} limit={20} />)

    const href = screen.getByRole("link", { name: /上一頁/ }).getAttribute("href")
    const params = new URLSearchParams(href!.split("?")[1])
    expect(params.get("direction")).toBe("prev")
    expect(params.get("seq")).toBe("2")
  })

  it("沒有游標時兩顆都是停用態，不是連結", () => {
    pathname = "/records"
    search = ""

    render(<Pagination meta={meta()} seq={1} limit={20} />)

    expect(screen.queryByRole("link")).not.toBeInTheDocument()
    expect(screen.getByText(/上一頁/).closest("span")).toHaveAttribute("aria-disabled", "true")
    expect(screen.getByText(/下一頁/).closest("span")).toHaveAttribute("aria-disabled", "true")
  })

  it("知道總筆數時顯示「第 n 頁／共 m 頁」", () => {
    pathname = "/records"
    search = ""

    render(<Pagination meta={meta({ total: 45 })} seq={2} limit={20} />)

    expect(screen.getByText("第 2 頁／共 3 頁")).toBeInTheDocument()
  })

  it("零筆資料仍然是「共 1 頁」", () => {
    // `Math.max(1, ...)` 的邊界: 空列表顯示「共 0 頁」會看起來像壞掉。
    pathname = "/records"
    search = ""

    render(<Pagination meta={meta({ total: 0 })} seq={1} limit={20} />)

    expect(screen.getByText("第 1 頁／共 1 頁")).toBeInTheDocument()
  })

  it("summary 接在頁數後面", () => {
    pathname = "/records"
    search = ""

    render(<Pagination meta={meta()} seq={1} limit={20} summary="已選 2 筆" />)

    expect(screen.getByText(/已選 2 筆/)).toBeInTheDocument()
  })
})
