import { describe, expect, it } from "vitest"
import { formatRequestError } from "@/shared/runtime/request-error"

const NOW = new Date("2026-11-11T03:04:05.678Z")

function format(error: unknown, headers: Record<string, string | string[] | undefined> = {}) {
  const request = { path: "/admin/users?name=secret", method: "GET", headers }
  return JSON.parse(formatRequestError(error, request, NOW))
}

describe("formatRequestError", () => {
  it("一行 JSON，欄位與 api 的 log 相同，帶 request id 與 digest", () => {
    const error = Object.assign(new Error("boom"), { digest: "1234567890" })

    const line = format(error, { "x-request-id": "abc123" })

    expect(line).toMatchObject({
      event: "unhandled_error",
      level: "error",
      timestamp: "2026-11-11T03:04:05.678Z",
      request_id: "abc123",
      digest: "1234567890",
      method: "GET",
      error: "Error: boom",
    })
    expect(line.stack).toContain("boom")
  })

  it("沒有 request id 與 digest 時是 -", () => {
    expect(format("plain failure")).toMatchObject({ request_id: "-", digest: "-" })
  })

  it("路徑不含 query string，敏感內容不長期留在 log 裡", () => {
    const line = format(new Error("x"))

    expect(line.path).toBe("/admin/users")
    expect(JSON.stringify(line)).not.toContain("secret")
  })

  it("整筆紀錄只佔一行，換行偽造不出另一筆", () => {
    const text = formatRequestError(new Error("line1\nline2"), { path: "/", method: "GET", headers: {} })

    expect(text.split("\n")).toHaveLength(1)
  })
})
