import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import AreaErrorBoundary from "@/app/(protected)/area-error"
import ErrorBoundary from "@/app/error"
import NotFoundView from "@/app/not-found-view"

describe("App Router 特殊頁面", () => {
  it("root 與區域 error 都能觸發 reset，且區域 error 使用 inline 版型（它在外殼裡面）", async () => {
    const rootReset = vi.fn()
    const protectedReset = vi.fn()
    const error = new Error("test")
    const { rerender } = render(<ErrorBoundary error={error} reset={rootReset} />)

    expect(screen.getByRole("main")).toHaveClass("message-page")
    expect(screen.getByRole("main")).not.toHaveClass("message-page--inline")
    await userEvent.click(screen.getByRole("button", { name: "重新載入" }))
    expect(rootReset).toHaveBeenCalledOnce()

    // 區域 error 畫在外殼的 <main> 裡, 自己不能再是 main (否則就是巢狀的主要地標)。
    rerender(<AreaErrorBoundary error={error} reset={protectedReset} />)
    expect(screen.queryByRole("main")).toBeNull()
    expect(screen.getByRole("heading", { name: "發生錯誤" }).closest(".message-page")).toHaveClass(
      "message-page--inline",
    )
    await userEvent.click(screen.getByRole("button", { name: "重新載入" }))
    expect(protectedReset).toHaveBeenCalledOnce()
  })

  it("伺服器端的錯誤顯示錯誤代碼，使用者回報時才查得到 log", () => {
    const error = Object.assign(new Error("test"), { digest: "3847261950" })
    render(<ErrorBoundary error={error} reset={vi.fn()} />)

    expect(screen.getByText("錯誤代碼：3847261950")).toBeInTheDocument()
  })

  it("沒有錯誤代碼時不顯示代碼列", () => {
    render(<ErrorBoundary error={new Error("test")} reset={vi.fn()} />)

    expect(screen.queryByText(/錯誤代碼/)).toBeNull()
  })

  // not-found.tsx 是 Server Component (要有 generateMetadata), 畫面本體拆在
  // not-found-view.tsx, 所以這裡測的是後者。
  it("not-found 保留自訂訊息與首頁連結", () => {
    render(<NotFoundView />)

    expect(screen.getByRole("heading", { name: "找不到頁面" })).toBeInTheDocument()
    expect(screen.getByText("這個網址不存在，或是內容已經被移除。")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "回首頁" })).toHaveAttribute("href", "/")
  })
})
