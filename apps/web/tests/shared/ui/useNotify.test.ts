import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { useNotify } from "@/shared/ui/hooks/useNotify"

describe("useNotify", () => {
  it("初始狀態是關閉且沒有訊息", () => {
    const { result } = renderHook(() => useNotify())

    expect(result.current.notify).toEqual({ open: false, message: "" })
  })

  it.each([
    ["notifyError", "error"],
    ["notifySuccess", "success"],
    ["notifyInfo", "info"],
  ] as const)("%s 會開啟通知並帶上 %s severity", (fnName, severity) => {
    const { result } = renderHook(() => useNotify())

    act(() => result.current[fnName]("訊息內容"))

    expect(result.current.notify).toEqual({
      open: true,
      message: "訊息內容",
      severity,
    })
  })

  it("closeNotify 只關閉 open，保留 message 與 severity", () => {
    // 保留訊息是刻意的: 通知元件關閉時通常有淡出動畫, 訊息在動畫期間被清掉會閃一下空白。
    const { result } = renderHook(() => useNotify())

    act(() => result.current.notifySuccess("已儲存"))
    act(() => result.current.closeNotify())

    expect(result.current.notify).toEqual({
      open: false,
      message: "已儲存",
      severity: "success",
    })
  })

  it("回傳的函式在 re-render 之間保持同一個參考", () => {
    // 這正是這個 hook 用 useCallback 包起來的理由 (見檔案註解): 呼叫端把它們放進
    // useEffect 依賴陣列時不該每次 render 都重跑, 否則只能靠 eslint-disable 繞過。
    const { result, rerender } = renderHook(() => useNotify())
    const first = result.current

    rerender()

    expect(result.current.notifyError).toBe(first.notifyError)
    expect(result.current.notifySuccess).toBe(first.notifySuccess)
    expect(result.current.notifyInfo).toBe(first.notifyInfo)
    expect(result.current.closeNotify).toBe(first.closeNotify)
  })

  it("狀態更新後函式參考仍然穩定", () => {
    const { result } = renderHook(() => useNotify())
    const before = result.current.closeNotify

    act(() => result.current.notifyError("壞了"))

    expect(result.current.closeNotify).toBe(before)
  })
})
