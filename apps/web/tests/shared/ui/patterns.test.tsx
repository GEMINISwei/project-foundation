import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MessagePage, MessagePageButton, MessagePageLink } from "@/shared/ui/feedback/MessagePage"
import RouteLoading from "@/shared/ui/feedback/RouteLoading"
import ActionMenu from "@/shared/ui/patterns/ActionMenu"
import FilterDialog, { useStatusFilterOptions } from "@/shared/ui/patterns/FilterDialog"
import ListPageHeader from "@/shared/ui/patterns/ListPageHeader"
import ListTableCard from "@/shared/ui/patterns/ListTableCard"
import Menu from "@/shared/ui/patterns/Menu"
import PageHeader from "@/shared/ui/patterns/PageHeader"
import StatusBadge from "@/shared/ui/patterns/StatusBadge"
import TableRow from "@/shared/ui/patterns/TableRow"

const routerPush = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => "/records",
  useRouter: () => ({ push: routerPush }),
  useSearchParams: () => new URLSearchParams("cursor=old&seq=3"),
}))

describe("shared list patterns", () => {
  beforeEach(() => routerPush.mockReset())

  it("ActionMenu 過濾空項目並執行所選動作", async () => {
    const action = vi.fn()
    render(<ActionMenu items={[null, false, { label: "編輯", onClick: action }]} />)

    await userEvent.click(screen.getByRole("button", { name: "操作選單" }))
    await userEvent.click(screen.getByRole("menuitem", { name: "編輯" }))

    expect(action).toHaveBeenCalledOnce()
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("Menu 用自訂的觸發內容與名稱，選完就收起來", async () => {
    const action = vi.fn()
    render(
      <Menu
        trigger={<span>王</span>}
        triggerLabel="帳號選單"
        placement="above"
        items={[{ label: "登出", onClick: action }]}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "帳號選單" }))
    await userEvent.click(screen.getByRole("menuitem", { name: "登出" }))

    expect(action).toHaveBeenCalledOnce()
    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("Menu 開啟時焦點移到第一個項目，方向鍵可以在項目間移動", async () => {
    render(
      <Menu
        trigger="⋯"
        triggerLabel="操作"
        items={[{ label: "編輯", onClick: vi.fn() }, { label: "刪除", onClick: vi.fn() }]}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    expect(screen.getByRole("menuitem", { name: "編輯" })).toHaveFocus()

    await userEvent.keyboard("{ArrowDown}")
    expect(screen.getByRole("menuitem", { name: "刪除" })).toHaveFocus()

    // 到底之後繞回第一個, 往上也一樣。
    await userEvent.keyboard("{ArrowDown}")
    expect(screen.getByRole("menuitem", { name: "編輯" })).toHaveFocus()
    await userEvent.keyboard("{ArrowUp}")
    expect(screen.getByRole("menuitem", { name: "刪除" })).toHaveFocus()
  })

  it("Menu 按 Escape 會關閉選單，焦點還給觸發按鈕", async () => {
    render(<Menu trigger="⋯" triggerLabel="操作" items={[{ label: "編輯", onClick: vi.fn() }]} />)

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    await userEvent.keyboard("{Escape}")

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "操作" })).toHaveFocus()
  })

  it("Menu 往上展開時以觸發點的上緣定位，不會蓋住觸發點", async () => {
    render(
      <Menu trigger="⋯" triggerLabel="帳號選單" placement="above" items={[{ label: "登出", onClick: vi.fn() }]} />,
    )
    const trigger = screen.getByRole("button", { name: "帳號選單" })
    trigger.parentElement!.getBoundingClientRect = () =>
      ({ top: 700, bottom: 740, left: 20, right: 60, width: 40, height: 40 }) as DOMRect

    await userEvent.click(trigger)

    const menu = screen.getByRole("menu")
    expect(menu.style.bottom).toBe(`${window.innerHeight - 700 + 4}px`)
    expect(menu.style.top).toBe("")
  })

  it("Menu 給了 sheetTitle 時開成以它為標題的面板，選完就收起來", async () => {
    const action = vi.fn()
    render(
      <Menu trigger="王" triggerLabel="帳號選單" sheetTitle="王小明" items={[{ label: "登出", onClick: action }]} />,
    )

    await userEvent.click(screen.getByRole("button", { name: "帳號選單" }))
    const sheet = screen.getByRole("dialog", { name: "王小明" })
    await userEvent.click(within(sheet).getByRole("menuitem", { name: "登出" }))

    expect(action).toHaveBeenCalledOnce()
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("Menu 的面板點遮罩會關閉", async () => {
    render(
      <Menu trigger="王" triggerLabel="帳號選單" sheetTitle="王小明" items={[{ label: "登出", onClick: vi.fn() }]} />,
    )

    await userEvent.click(screen.getByRole("button", { name: "帳號選單" }))
    await userEvent.click(screen.getByRole("dialog").parentElement!)

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("Menu 的面板按關閉鈕會關閉", async () => {
    render(
      <Menu trigger="王" triggerLabel="帳號選單" sheetTitle="王小明" items={[{ label: "登出", onClick: vi.fn() }]} />,
    )

    await userEvent.click(screen.getByRole("button", { name: "帳號選單" }))
    await userEvent.click(screen.getByRole("button", { name: "關閉" }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("Menu 再按一次觸發按鈕會收起選單", async () => {
    render(<Menu trigger="⋯" triggerLabel="操作" items={[{ label: "編輯", onClick: vi.fn() }]} />)

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    await userEvent.click(screen.getByRole("button", { name: "操作" }))

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("Menu 按方向鍵以外的鍵不移動焦點", async () => {
    render(
      <Menu
        trigger="⋯"
        triggerLabel="操作"
        items={[{ label: "編輯", onClick: vi.fn() }, { label: "刪除", onClick: vi.fn() }]}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    await userEvent.keyboard("a")

    expect(screen.getByRole("menuitem", { name: "編輯" })).toHaveFocus()
  })

  it("Menu 點選單外面會關閉", async () => {
    render(<Menu trigger="⋯" triggerLabel="操作" items={[{ label: "編輯", onClick: vi.fn() }]} />)

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    expect(screen.getByRole("menu")).toBeInTheDocument()
    await userEvent.click(document.body)

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("Menu 捲動頁面時會關閉", async () => {
    // 選單以 fixed 定位在觸發點旁邊, 捲動後位置就對不上了。
    render(<Menu trigger="⋯" triggerLabel="操作" items={[{ label: "編輯", onClick: vi.fn() }]} />)

    await userEvent.click(screen.getByRole("button", { name: "操作" }))
    fireEvent.scroll(window)

    expect(screen.queryByRole("menu")).not.toBeInTheDocument()
  })

  it("Menu 沒有可見項目時不顯示", () => {
    render(<Menu trigger="⋯" triggerLabel="操作" items={[null, false]} />)

    expect(screen.queryByRole("button", { name: "操作" })).not.toBeInTheDocument()
  })

  it("FilterDialog 沒有任何條件時導向不帶問號的原網址", async () => {
    const onClose = vi.fn()
    render(
      <FilterDialog
        title="篩選"
        open
        onClose={onClose}
        fields={[
          { name: "name", label: "名稱", type: "text" },
          { name: "is_disabled", label: "狀態", type: "select", options: [{ value: "", label: "全部" }] },
        ]}
        initialValues={{ name: "   ", is_disabled: "" }}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "篩選" }))

    expect(routerPush).toHaveBeenCalledWith("/records")
  })

  it("FilterDialog 沒給初始值的欄位當成空的，送出時不放進網址", async () => {
    render(
      <FilterDialog
        title="篩選"
        open
        onClose={vi.fn()}
        fields={[
          { name: "name", label: "名稱", type: "text" },
          { name: "is_disabled", label: "狀態", type: "select", options: [{ value: "", label: "全部" }] },
        ]}
        initialValues={{}}
      />,
    )

    expect(screen.getByLabelText("名稱")).toHaveValue("")
    await userEvent.click(screen.getByRole("button", { name: "篩選" }))

    expect(routerPush).toHaveBeenCalledWith("/records")
  })

  it("FilterDialog 按重置會清空所有欄位", async () => {
    render(
      <FilterDialog
        title="篩選"
        open
        onClose={vi.fn()}
        fields={[{ name: "name", label: "名稱", type: "text" }]}
        initialValues={{ name: "demo" }}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "重置" }))

    expect(screen.getByLabelText("名稱")).toHaveValue("")
  })

  it("FilterDialog 關閉時呼叫 onClose", async () => {
    const onClose = vi.fn()
    render(
      <FilterDialog
        title="篩選"
        open
        onClose={onClose}
        fields={[{ name: "name", label: "名稱", type: "text" }]}
        initialValues={{ name: "" }}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "關閉" }))

    expect(onClose).toHaveBeenCalledOnce()
    expect(routerPush).not.toHaveBeenCalled()
  })

  it("ListPageHeader 按重整會導向清掉分頁游標的網址，有 createAction 時顯示新增按鈕", async () => {
    const create = vi.fn()
    const { rerender } = render(
      <ListPageHeader
        title="項目"
        subtitle="管理項目"
        showReset
        onFilter={vi.fn()}
        createAction={{ label: "新增項目", onClick: create }}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: "重整" }))
    expect(routerPush).toHaveBeenCalledWith("/records")
    await userEvent.click(screen.getByRole("button", { name: "新增項目" }))
    expect(create).toHaveBeenCalledOnce()

    rerender(<ListPageHeader title="項目" subtitle="管理項目" showReset={false} onFilter={vi.fn()} />)
    expect(screen.queryByRole("button", { name: "重整" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "新增項目" })).not.toBeInTheDocument()
  })

  it("FilterDialog 正規化輸入並導向篩選網址", async () => {
    const onClose = vi.fn()
    // 狀態選項現在是 hook (label 跟著語系走), 所以在元件裡取用。
    // 沒有 LocaleProvider 時 useLocale 回預設語系, 這裡拿到的就是中文標籤。
    function Subject() {
      return (
        <FilterDialog
          title="篩選"
          open
          onClose={onClose}
          fields={[
            { name: "name", label: "名稱", type: "text" },
            { name: "is_disabled", label: "狀態", type: "select", options: useStatusFilterOptions() },
          ]}
          initialValues={{ name: "", is_disabled: "" }}
        />
      )
    }
    render(<Subject />)

    await userEvent.type(screen.getByLabelText("名稱"), "  demo  ")
    await userEvent.selectOptions(screen.getByLabelText("狀態"), "true")
    await userEvent.click(screen.getByRole("button", { name: "篩選" }))

    expect(routerPush).toHaveBeenCalledWith("/records?name=demo&is_disabled=true")
    expect(onClose).toHaveBeenCalledOnce()
  })

  it("列表外殼顯示欄名、資料與空狀態", () => {
    const { rerender } = render(
      <ListTableCard headers={["名稱"]} isEmpty={false} emptyText="沒有資料">
        <TableRow><td>範例</td></TableRow>
      </ListTableCard>,
    )
    // TableRow 存在的理由就是這個 class: 窄螢幕時把表格列轉成卡片。模組不自己
    // import UI kit 的樣式檔, 所以這裡是唯一會發現「class 掉了」的地方。
    expect(screen.getByRole("row", { name: "範例" }).className).toBeTruthy()
    expect(screen.getByRole("columnheader", { name: "名稱" })).toBeInTheDocument()
    expect(screen.getByText("範例")).toBeInTheDocument()

    rerender(<ListTableCard headers={["名稱"]} isEmpty emptyText="沒有資料">{null}</ListTableCard>)
    expect(screen.getByText("沒有資料")).toBeInTheDocument()
  })

  it("頁首、狀態與回饋元件保留可存取文字", async () => {
    const action = vi.fn()
    const { rerender } = render(
      <PageHeader
        title="項目"
        subtitle="管理項目"
        actions={<button type="button">新增</button>}
        mobileActions={[{ label: "新增", onClick: action }]}
      />,
    )
    expect(screen.getByRole("heading", { name: "項目" })).toBeInTheDocument()
    expect(screen.getByText("管理項目")).toBeInTheDocument()

    rerender(<StatusBadge label="啟用" variant="success" />)
    const badge = screen.getByText("啟用")
    expect(badge).toBeInTheDocument()
    expect(badge.className.trim().split(/\s+/)).toHaveLength(2)

    rerender(
      <MessagePage title="找不到" description="此頁不存在">
        <MessagePageButton onClick={action}>重試</MessagePageButton>
        <MessagePageLink href="/">首頁</MessagePageLink>
      </MessagePage>,
    )
    await userEvent.click(screen.getByRole("button", { name: "重試" }))
    expect(action).toHaveBeenCalledOnce()
    expect(screen.getByRole("link", { name: "首頁" })).toHaveAttribute("href", "/")
    // 整頁的訊息自己就是頁面主體, 要提供 main 地標。
    expect(screen.getByRole("main")).toHaveClass("message-page")

    // inline 版畫在外殼的 <main> 裡 (`app/(protected)/area-error.tsx`), 再出一個 main 就是兩個
    // 主要地標 —— 螢幕閱讀器會看到兩塊「主要內容」。
    rerender(<MessagePage title="發生錯誤" description="請稍後再試" inline />)
    expect(screen.queryByRole("main")).toBeNull()
    expect(screen.getByText("發生錯誤").closest(".message-page")).toHaveClass("message-page--inline")

    rerender(<RouteLoading text="讀取資料" />)
    expect(screen.getByText("讀取資料")).toBeInTheDocument()
  })
})
