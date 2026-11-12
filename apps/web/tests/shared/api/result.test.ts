import { describe, expect, it } from "vitest"
import { errorMessage, fieldErrors } from "@/shared/api/result"
import type { ApiResult } from "@/shared/api/types"

const failure = (message: string, requestId: string, fields = {}): ApiResult<unknown> => ({
  ok: false,
  error: { status: 400, code: "x", message, requestId, fields },
})

describe("errorMessage", () => {
  it("成功的結果沒有錯誤訊息", () => {
    expect(errorMessage({ ok: true, data: 1 }, "失敗")).toBe("")
  })

  it("用後端的訊息並附上 request id，方便使用者回報", () => {
    expect(errorMessage(failure("角色名稱已存在", "abc123"), "失敗")).toBe("角色名稱已存在 (abc123)")
  })

  it("後端沒給訊息時用預設訊息；沒有 request id 就不附", () => {
    expect(errorMessage(failure("", ""), "失敗")).toBe("失敗")
  })
})

describe("fieldErrors", () => {
  it("只有失敗的結果有欄位錯誤", () => {
    expect(fieldErrors({ ok: true, data: 1 })).toEqual({})
    expect(fieldErrors(failure("x", "", { name: "必填" }))).toEqual({ name: "必填" })
  })
})
