/**
 * `LocaleProvider` → `useT` → 字典這條線, 以及**拿不到 provider 時**的退路
 * (`useLocaleFromCookie`)。
 *
 * 其他測試 (`dictionary.test.ts`) 測的是 `translate()` 這個純函式, 證明不了 React 這一半
 * 真的接上了。而這一層失敗的方式很安靜: provider 沒掛上時 `useLocale()` 會回預設語系,
 * 整個 app 看起來「正常」, 只是永遠是中文 —— 切換語言毫無反應。
 */

import { render, renderHook, screen } from "@testing-library/react"
import { renderToString } from "react-dom/server"
import { afterEach, describe, expect, it } from "vitest"
import { Loading } from "@/shared/ui"
import { LocaleProvider, useLocaleFromCookie, useT } from "@/shared/i18n/context"
import { defineMessages } from "@/shared/i18n/dictionary"
import { DEFAULT_LOCALE, LOCALE_COOKIE } from "@/shared/i18n/locale"

const messages = defineMessages({
  zh: { greet: "你好，{name}" },
  en: { greet: "Hello, {name}" },
})

function Subject() {
  const t = useT(messages)

  return <span>{t("greet", { name: "Ada" })}</span>
}

describe("LocaleProvider", () => {
  it("provider 的語系決定字典取哪一份", () => {
    const { rerender } = render(
      <LocaleProvider locale="en"><Subject /></LocaleProvider>,
    )
    expect(screen.getByText("Hello, Ada")).toBeInTheDocument()

    rerender(<LocaleProvider locale="zh"><Subject /></LocaleProvider>)
    expect(screen.getByText("你好，Ada")).toBeInTheDocument()
  })

  it("沒有 provider 時退回預設語系", () => {
    // 其他元件測試全都依賴這個行為 (它們不掛 provider 卻斷言中文字串),
    // 但沒有人釘住它。改掉 createContext 的預設值會讓那些測試一起變成假通過。
    render(<Subject />)

    expect(screen.getByText(messages[DEFAULT_LOCALE].greet.replace("{name}", "Ada"))).toBeInTheDocument()
  })

  it("生產程式碼裡的 UI kit 元件真的跟著 provider 走", () => {
    // 用真實元件而不只是 fixture: 證明「kit 內部的 useT(uiMessages)」這條接線存在,
    // 而不是只有測試自己搭的那一條。
    //
    // 這裡斷言字面值而不是引用 `shared/ui/i18n`: 那份字典是 UI kit 的實作細節,
    // 只能從 `@/shared/ui` 這個公開面取用 (dependency-cruiser 會擋)。
    // 而這支測試要驗的本來就是「使用者看到什麼」, 字面值正是對的表達方式。
    render(<LocaleProvider locale="en"><Loading /></LocaleProvider>)

    expect(screen.getByText("Loading")).toBeInTheDocument()
    expect(screen.queryByText("載入中")).not.toBeInTheDocument()
  })
})

describe("useLocaleFromCookie", () => {
  // document.cookie 是測試環境裡的共用狀態, 每個 case 自己設、跑完清掉。
  afterEach(() => {
    document.cookie = `${LOCALE_COOKIE}=; max-age=0; path=/`
  })

  function setCookie(raw: string) {
    document.cookie = raw
  }

  it("讀 cookie 裡的語系", () => {
    setCookie(`${LOCALE_COOKIE}=en`)

    const { result } = renderHook(() => useLocaleFromCookie())

    expect(result.current).toBe("en")
  })

  it("沒有 cookie 時回預設語系", () => {
    const { result } = renderHook(() => useLocaleFromCookie())

    expect(result.current).toBe(DEFAULT_LOCALE)
  })

  it("cookie 是不認得的值時回預設語系", () => {
    // 使用者可以自己改 cookie (這一份刻意不是 httpOnly, 見 context.tsx 的註解)。
    // 少了 isLocale 的檢查, 字典查詢會拿到 undefined, 整頁變成空字串。
    setCookie(`${LOCALE_COOKIE}=klingon`)

    const { result } = renderHook(() => useLocaleFromCookie())

    expect(result.current).toBe(DEFAULT_LOCALE)
  })

  it("同名前綴的其他 cookie 不會被誤認", () => {
    // `locale_preview=en` 不是 `locale=en`。用 includes/indexOf 之類的寫法會中招,
    // 而症狀是「某些使用者的語言莫名其妙固定成某一種」。
    setCookie(`${LOCALE_COOKIE}_preview=en`)
    setCookie("other=zh")

    const { result } = renderHook(() => useLocaleFromCookie())

    expect(result.current).toBe(DEFAULT_LOCALE)
  })

  it("多個 cookie 並存時挑得出正確那一個", () => {
    setCookie("session=abc")
    setCookie(`${LOCALE_COOKIE}=en`)
    setCookie("theme=dark")

    const { result } = renderHook(() => useLocaleFromCookie())

    expect(result.current).toBe("en")
  })

  it("伺服器端渲染時用預設語系，不去碰 document", () => {
    // 這是 useSyncExternalStore 分成兩份 snapshot 的原因: 伺服器端沒有 document,
    // 直接讀會拋錯; 而如果 server snapshot 也去猜語系, client 第一次 render 的結果
    // 會跟 SSR 不一致, 變成 hydration mismatch。
    // 用 renderToString 才走得到 server snapshot 那條路徑, jsdom 裡的 render 走不到。
    function Subject() {
      return <span>{useLocaleFromCookie()}</span>
    }

    setCookie(`${LOCALE_COOKIE}=en`)

    expect(renderToString(<Subject />)).toContain(DEFAULT_LOCALE)
  })
})
