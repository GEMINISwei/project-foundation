/**
 * 列表頁「動作完成之後要做什麼」這條動線。
 *
 * 為什麼值得測: 兩個列表頁 (users/roles) 都靠它, 而它把三件必須一起發生的事
 * 綁在一起 —— 關掉對話框、跳通知、`router.refresh()` 重抓伺服器資料。少掉最後一項的話
 * 症狀特別容易被誤判成「後端沒寫進去」: 資料其實已經改了, 只是畫面還是舊的那一份。
 *
 * 順序也有意義: 先 cleanup (關對話框) 再 refresh。反過來的話會在對話框還開著的時候
 * 觸發整頁重繪, 使用者會看到對話框裡的內容閃一下。
 */

import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { useListFeedback } from "@/shared/ui/hooks/useListFeedback"

const refresh = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}))

describe("useListFeedback", () => {
  it("成功時依序關對話框、跳通知、重抓資料", () => {
    const calls: string[] = []
    refresh.mockReset()
    refresh.mockImplementation(() => calls.push("refresh"))
    const cleanup = vi.fn(() => calls.push("cleanup"))

    const { result } = renderHook(() => useListFeedback(cleanup))
    act(() => result.current.handleSuccess("已儲存"))

    expect(calls).toEqual(["cleanup", "refresh"])
    expect(result.current.notify).toEqual({
      open: true,
      message: "已儲存",
      severity: "success",
    })
  })

  it("沒有傳 cleanup 時照樣運作", () => {
    // 呼叫端不一定有對話框要關 (例如列表上的行內動作), 那時不該炸。
    refresh.mockReset()

    const { result } = renderHook(() => useListFeedback())
    act(() => result.current.handleSuccess("已刪除"))

    expect(refresh).toHaveBeenCalledOnce()
    expect(result.current.notify.severity).toBe("success")
  })

  it("失敗時只跳錯誤通知，不重抓資料", () => {
    // 失敗代表資料沒變, refresh 只會多打一輪 API; 更糟的是它會把使用者剛填、
    // 還沒送出成功的表單狀態一起洗掉。
    refresh.mockReset()
    const cleanup = vi.fn()

    const { result } = renderHook(() => useListFeedback(cleanup))
    act(() => result.current.handleError("名稱重複"))

    expect(refresh).not.toHaveBeenCalled()
    expect(cleanup).not.toHaveBeenCalled()
    expect(result.current.notify).toEqual({
      open: true,
      message: "名稱重複",
      severity: "error",
    })
  })
})
