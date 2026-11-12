import { act, renderHook, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { ApiResult } from "@/shared/api/types"
import { useActionSubmit } from "@/shared/ui/hooks/useActionSubmit"

const failure = (overrides: Partial<Extract<ApiResult<unknown>, { ok: false }>["error"]> = {}) => ({
  ok: false as const,
  error: { status: 400, code: "x", message: "", requestId: "", fields: {}, ...overrides },
})

function setup() {
  const onSuccess = vi.fn()
  const onError = vi.fn()
  const { result } = renderHook(() => useActionSubmit())
  return { onSuccess, onError, result }
}

describe("useActionSubmit", () => {
  it("成功會走 onSuccess，不會呼叫 onError", async () => {
    const { onSuccess, onError, result } = setup()

    act(() => {
      result.current.submit(() => Promise.resolve({ ok: true, data: null }), { onSuccess, onError })
    })

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
    expect(onError).not.toHaveBeenCalled()
  })

  it("失敗會走 onError，訊息是後端給的並附上 request id", async () => {
    const { onSuccess, onError, result } = setup()

    act(() => {
      result.current.submit(
        () => Promise.resolve(failure({ message: "帳號已存在", requestId: "abc123" })),
        { onSuccess, onError },
      )
    })

    await waitFor(() => expect(onError).toHaveBeenCalledWith("帳號已存在 (abc123)"))
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it("後端沒給訊息時用呼叫端的預設訊息", async () => {
    const { onSuccess, onError, result } = setup()

    act(() => {
      result.current.submit(() => Promise.resolve(failure()), {
        onSuccess,
        onError,
        errorFallback: "建立失敗",
      })
    })

    await waitFor(() => expect(onError).toHaveBeenCalledWith("建立失敗"))
  })

  it("欄位錯誤可以依欄位名取出，下一次送出時清掉", async () => {
    const { onSuccess, onError, result } = setup()

    act(() => {
      result.current.submit(
        () => Promise.resolve(failure({ fields: { name: "必填" } })),
        { onSuccess, onError },
      )
    })
    await waitFor(() => expect(result.current.fieldError("name")).toBe("必填"))
    expect(result.current.fieldError("other")).toBeUndefined()

    act(() => {
      result.current.submit(() => Promise.resolve({ ok: true, data: null }), { onSuccess, onError })
    })
    await waitFor(() => expect(result.current.fieldError("name")).toBeUndefined())
  })

  it("clearFieldErrors 清掉欄位錯誤", async () => {
    const { onSuccess, onError, result } = setup()

    act(() => {
      result.current.submit(
        () => Promise.resolve(failure({ fields: { name: "必填" } })),
        { onSuccess, onError },
      )
    })
    await waitFor(() => expect(result.current.fieldError("name")).toBe("必填"))
    act(() => result.current.clearFieldErrors())

    expect(result.current.fieldError("name")).toBeUndefined()
  })

  it("送出中再次送出不會重複執行", async () => {
    const { onSuccess, onError, result } = setup()
    const { promise, resolve } = Promise.withResolvers<ApiResult<null>>()
    const run = vi.fn(() => promise)

    act(() => {
      result.current.submit(run, { onSuccess, onError })
      result.current.submit(run, { onSuccess, onError })
    })
    await act(async () => resolve({ ok: true, data: null }))

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
    expect(run).toHaveBeenCalledTimes(1)
  })

  it("動作本身丟出例外（斷線）時顯示錯誤，而且之後還能再送出", async () => {
    const { onSuccess, onError, result } = setup()
    const crash = vi.fn(() => Promise.reject(new Error("network down")))

    act(() => {
      result.current.submit(crash, { onSuccess, onError, errorFallback: "儲存失敗" })
    })
    await waitFor(() => expect(onError).toHaveBeenCalledWith("儲存失敗"))
    act(() => {
      result.current.submit(() => Promise.resolve({ ok: true, data: null }), { onSuccess, onError })
    })

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
  })
})
