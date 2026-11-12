import { act, renderHook, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { ApiResult } from "@/shared/api/types"
import { useLoginForm } from "@/modules/auth/ui/useLoginForm"

const { loginUser } = vi.hoisted(() => ({ loginUser: vi.fn() }))

vi.mock("@/modules/auth/actions", () => ({ loginUser }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

describe("useLoginForm", () => {
  // 連按 Enter 時兩次送出可能在畫面鎖住之前就到了, 每一次失敗的登入都會算進限流。
  it("登入送出中再次送出不會再呼叫 loginUser", async () => {
    const { promise, resolve } = Promise.withResolvers<ApiResult<null>>()
    loginUser.mockReturnValue(promise)
    const { result } = renderHook(() => useLoginForm({}))

    act(() => {
      result.current.changeValue("username", "admin")
    })
    act(() => {
      result.current.changeValue("password", "password-123")
    })
    act(() => {
      result.current.submit()
      result.current.submit()
    })
    await act(async () => resolve({ ok: true, data: null }))

    await waitFor(() => expect(result.current.isPending).toBe(false))
    expect(loginUser).toHaveBeenCalledTimes(1)
  })
})
