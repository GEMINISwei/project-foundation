/**
 * 通知登記簿: `Notify` (登記) 與 `NotifyViewport` (渲染) 之間那份**模組層級狀態**。
 *
 * 為什麼值得專門測: `useNotify` 有測試, 但它只是每個頁面自己的狀態容器; 真正決定
 * 「使用者到底看到幾則、看到哪一則」的是這裡的登記簿, 而它是全站唯一一份、跨元件共用的
 * 可變狀態。壞掉的方式都很安靜 —— 重複 upsert 變成追加, 畫面上就疊出兩張一樣的卡片;
 * unmount 沒清掉, 換頁之後舊訊息還黏在畫面上; 自動關閉的 timer 沒接好, 通知就再也不消失。
 * 這幾種都不會讓任何測試或型別檢查變紅。
 *
 * **登記簿是模組層級狀態, 測試之間會互相污染。** Testing Library 的自動 cleanup 會 unmount
 * 元件, 而 `Notify` 的 unmount effect 會把自己從登記簿移除 —— 這條路徑本身就是下面在測的
 * 東西之一, 所以這裡刻意不另外寫手動清理: 真的壞掉時, 後面的測試會跟著紅, 那正是我們要的
 * 訊號。
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { act } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Notify, NotifyViewport, type NotifyProps } from "@/shared/ui"

function Subject(props: Partial<NotifyProps> & { open: boolean }) {
  const { open, message = "已儲存", ...rest } = props

  return (
    <>
      <Notify open={open} message={message} {...rest} />
      <NotifyViewport />
    </>
  )
}

afterEach(() => vi.useRealTimers())

describe("通知登記簿", () => {
  it("open 時把訊息登記進去，viewport 才看得到", () => {
    render(<Subject open message="已儲存" />)

    expect(screen.getByRole("alert")).toHaveTextContent("已儲存")
  })

  it("沒有任何通知時 viewport 不渲染任何東西", () => {
    render(<NotifyViewport />)

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("同一個 Notify 改訊息是取代，不是再登記一則", () => {
    // upsert 而不是 append: 少了這條, 連續兩次通知 (例如「儲存中」→「已儲存」)
    // 會在畫面上疊成兩張卡片, 而且舊的那張永遠不會消失。
    const { rerender } = render(<Subject open message="儲存中" />)

    rerender(<Subject open message="已儲存" />)

    expect(screen.getAllByRole("alert")).toHaveLength(1)
    expect(screen.getByRole("alert")).toHaveTextContent("已儲存")
  })

  it("兩個不同的 Notify 各自登記一則", () => {
    render(
      <>
        <Notify open message="第一則" />
        <Notify open message="第二則" />
        <NotifyViewport />
      </>,
    )

    expect(screen.getAllByRole("alert")).toHaveLength(2)
  })

  it("兩則通知時改其中一則的訊息，另一則不受影響", () => {
    const { rerender } = render(
      <>
        <Notify open message="第一則" />
        <Notify open message="第二則" />
        <NotifyViewport />
      </>,
    )

    rerender(
      <>
        <Notify open message="第一則" />
        <Notify open message="第二則已更新" />
        <NotifyViewport />
      </>,
    )

    const alerts = screen.getAllByRole("alert")
    expect(alerts).toHaveLength(2)
    expect(alerts[0]).toHaveTextContent("第一則")
    expect(alerts[1]).toHaveTextContent("第二則已更新")
  })

  it("open 轉 false 會把它從登記簿移除", () => {
    const { rerender } = render(<Subject open message="已儲存" />)

    rerender(<Subject open={false} message="已儲存" />)

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("unmount 會把它從登記簿移除", () => {
    // 換頁時 Notify 跟著卸載, 但 viewport 活在 layout 裡不會重建。
    // 少了 unmount 的清理, 上一頁的通知會黏在新頁面上。
    const { unmount } = render(<Subject open message="已儲存" />)
    render(<NotifyViewport />)

    unmount()

    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("關掉其中一則，另一則留著", () => {
    // 多則同時在畫面上時, 移除是**按 id** 而不是清空。寫成清空的話,
    // 使用者按掉一則會連旁邊那則一起消失。
    function Pair({ firstOpen }: { firstOpen: boolean }) {
      return (
        <>
          <Notify open={firstOpen} message="第一則" />
          <Notify open message="第二則" />
          <NotifyViewport />
        </>
      )
    }
    const { rerender } = render(<Pair firstOpen />)

    rerender(<Pair firstOpen={false} />)

    expect(screen.getByRole("alert")).toHaveTextContent("第二則")
    // 重複關閉同一則不應該把畫面弄壞 (會走到 removeNotify 找不到目標的那條路徑)。
    // 註: 那條路徑只是省掉一次無謂的通知, 從外部觀察不到差別 —— 這裡只保證它不出事,
    // 沒有把它釘住。
    rerender(<Pair firstOpen={false} />)
    expect(screen.getAllByRole("alert")).toHaveLength(1)
  })

  it.each([
    ["success", "成功"],
    ["error", "失敗"],
    ["info", "提示"],
    ["warning", "警告"],
  ] as const)("severity=%s 也渲染得出來", (severity, message) => {
    // 四種 severity 各查兩張表 (icon 與 class)。少一個 key 的話 React 會渲染出
    // `undefined`: 畫面上是一則沒有圖示的通知, 不會拋錯。
    render(<Subject open message={message} severity={severity} />)

    expect(screen.getByRole("alert")).toHaveTextContent(message)
  })

  it("關閉鈕呼叫該則自己的 onOpenChange", async () => {
    const onOpenChange = vi.fn()
    render(<Subject open message="已儲存" onOpenChange={onOpenChange} />)

    await userEvent.click(screen.getByRole("button", { name: "關閉" }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("預設 5 秒後自動關閉", () => {
    vi.useFakeTimers()
    const onOpenChange = vi.fn()
    render(<Subject open message="已儲存" onOpenChange={onOpenChange} />)

    act(() => void vi.advanceTimersByTime(4999))
    expect(onOpenChange).not.toHaveBeenCalled()

    act(() => void vi.advanceTimersByTime(1))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("duration 可以覆寫自動關閉的時間", () => {
    vi.useFakeTimers()
    const onOpenChange = vi.fn()
    render(<Subject open message="已儲存" duration={100} onOpenChange={onOpenChange} />)

    act(() => void vi.advanceTimersByTime(100))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("關閉狀態不會排自動關閉的 timer", () => {
    vi.useFakeTimers()
    const onOpenChange = vi.fn()
    render(<Subject open={false} message="已儲存" onOpenChange={onOpenChange} />)

    act(() => void vi.advanceTimersByTime(10_000))

    expect(onOpenChange).not.toHaveBeenCalled()
  })
})
