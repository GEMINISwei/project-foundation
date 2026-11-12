import { render } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({ headers: new Map<string, string>() }))

vi.mock("next/headers", () => ({
  headers: async () => ({ get: (name: string) => state.headers.get(name) ?? null }),
}))

import { ClientErrorReporter } from "@/shared/runtime/ClientErrorReporter"
import { reportClientError } from "@/shared/runtime/client-error"

function logged() {
  return vi.mocked(console.error).mock.calls.map(([line]) => JSON.parse(String(line)))
}

beforeEach(() => {
  state.headers.clear()
  vi.spyOn(console, "error").mockImplementation(() => {})
})

describe("reportClientError", () => {
  it("記成一行 JSON，帶追蹤 id 與瀏覽器資訊，路徑不含 query string", async () => {
    state.headers.set("x-request-id", "trace-7")
    state.headers.set("user-agent", "TestBrowser/1.0")

    await reportClientError({ message: "x is not a function", stack: "at a.js:1", path: "/a?b=1" })

    expect(logged()).toEqual([
      expect.objectContaining({
        event: "client_error",
        level: "error",
        request_id: "trace-7",
        message: "x is not a function",
        stack: "at a.js:1",
        path: "/a",
        user_agent: "TestBrowser/1.0",
      }),
    ])
  })

  it("內容來自瀏覽器：過長的截斷，不是字串的當成空的", async () => {
    await reportClientError({
      message: "m".repeat(5000),
      stack: { evil: true } as unknown as string,
      path: "/",
    })

    const [entry] = logged()
    expect(entry.message).toHaveLength(2000)
    expect(entry.stack).toBe("")
    expect(entry.request_id).toBe("-")
  })
})

describe("ClientErrorReporter", () => {
  it("回報沒被接住的錯誤，同一個畫面最多五次", async () => {
    const { unmount } = render(<ClientErrorReporter />)

    for (let index = 0; index < 8; index += 1) {
      // 只帶 message: 帶著 Error 物件的事件會被測試框架當成它自己沒接住的錯誤。
      window.dispatchEvent(new ErrorEvent("error", { message: `boom ${index}` }))
    }
    await vi.waitFor(() => expect(logged()).toHaveLength(5))
    expect(logged()[0]).toMatchObject({ event: "client_error", message: "boom 0" })

    unmount()
    window.dispatchEvent(new ErrorEvent("error", { message: "after unmount" }))
    await Promise.resolve()
    expect(logged()).toHaveLength(5)
  })

  it("沒被處理的 Promise 拒絕也會回報", async () => {
    render(<ClientErrorReporter />)

    const event = new Event("unhandledrejection") as PromiseRejectionEvent
    Object.defineProperty(event, "reason", { value: "plain reason" })
    window.dispatchEvent(event)

    await vi.waitFor(() => expect(logged()).toHaveLength(1))
    expect(logged()[0].message).toBe("plain reason")
  })
})
