import { describe, expect, it } from "vitest"
import type { ApiResult } from "@/shared/api/types"
import { withoutData } from "@/shared/session/token-response"

describe("withoutData", () => {
  it("成功的結果不帶任何內容回瀏覽器", () => {
    const result: ApiResult<{ access_token: string }> = { ok: true, data: { access_token: "jwt" } }

    const stripped = withoutData(result)

    expect(JSON.stringify(stripped)).not.toContain("jwt")
    expect(stripped).toEqual({ ok: true, data: null })
  })

  it("失敗的結果原樣傳回", () => {
    const result: ApiResult<{ access_token: string }> = {
      ok: false,
      error: { status: 401, code: "users.invalid_credentials", message: "x", requestId: "r", fields: {} },
    }

    expect(withoutData(result)).toBe(result)
  })
})
