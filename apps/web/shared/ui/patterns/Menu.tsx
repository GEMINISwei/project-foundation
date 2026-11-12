"use client"

import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { Modal } from "../dialogs"
import { cls } from "../internals"
import styles from "../styles/action-menu.module.css"

/**
 * 選單本體的寬度與離視窗邊緣的最小間距。
 *
 * 位置要用 JS 算 (`position: fixed` 才不會被表格的 `overflow` 裁掉), 但寬度住在
 * CSS 的 `.dropdown { min-width }`。兩邊必須一致, 所以在這裡寫成有名字的常數並
 * 標明對應關係。**不要就地寫 `window.innerWidth - 148`** —— 改了 CSS 的 min-width
 * 就會讓右邊界的夾擠算錯, 而且不會有任何訊號。
 */
const DROPDOWN_WIDTH = 140
const VIEWPORT_MARGIN = 8
const TRIGGER_GAP = 4

export type MenuItem = {
  icon?: React.ReactNode
  label: string
  color?: "default" | "error"
  onClick: () => void
}

type MenuProps = {
  items: (MenuItem | null | false | undefined)[]
  /** 觸發按鈕裡的內容 (圖示、頭像…)。 */
  trigger: React.ReactNode
  /** 觸發按鈕的無障礙名稱: 內容只有圖示時, 這是唯一說得出它是什麼的地方。 */
  triggerLabel: string
  /** 觸發按鈕的外觀。沒給就用 kit 的圖示按鈕。 */
  triggerClassName?: string
  /** 貼在畫面底部的觸發點 (側欄底部、手機的底部導覽) 要往上展開, 否則選單會被切掉。 */
  placement?: "below" | "above"
  /** 撐滿外層 (例如側欄底部、底部導覽的一格); 預設跟內容一樣寬。 */
  fullWidth?: boolean
  /**
   * 給了就不開下拉, 改開以它為標題的面板 (手機上是從底部浮出、帶遮罩的 sheet)。
   * 給手指點的觸發點用: 下拉的項目對手指太小, 也看不出點哪裡能關掉。
   */
  sheetTitle?: string
}

type Position = { left: number; top?: number; bottom?: number }

/** 下拉選單的鍵盤操作: Escape 關閉, 上下鍵在項目間移動 (到頭繞回另一端)。 */
function handleMenuKeyDown(event: React.KeyboardEvent<HTMLDivElement>, close: () => void) {
  if (event.key === "Escape") {
    event.preventDefault()
    close()
    return
  }
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return
  event.preventDefault()
  const menuItems = [...event.currentTarget.querySelectorAll<HTMLElement>("[role='menuitem']")]
  const current = menuItems.indexOf(document.activeElement as HTMLElement)
  const step = event.key === "ArrowDown" ? 1 : -1
  menuItems[(current + step + menuItems.length) % menuItems.length]?.focus()
}

export default function Menu({
  items,
  trigger,
  triggerLabel,
  triggerClassName,
  placement = "below",
  fullWidth = false,
  sheetTitle,
}: MenuProps) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<Position>({ top: 0, left: 0 })
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const visibleItems = items.filter((item): item is MenuItem => Boolean(item))

  function toggleOpen() {
    if (!open && ref.current) {
      const rect = ref.current.getBoundingClientRect()
      const left = Math.min(
        Math.max(VIEWPORT_MARGIN, rect.left),
        window.innerWidth - DROPDOWN_WIDTH - VIEWPORT_MARGIN,
      )
      setPosition(
        placement === "above"
          ? { left, bottom: window.innerHeight - rect.top + TRIGGER_GAP }
          : { left, top: rect.bottom + TRIGGER_GAP },
      )
    }
    setOpen((current) => !current)
  }

  useEffect(() => {
    // 面板自己有遮罩處理點外面關閉; 面板內捲動也不該把它關掉。
    if (!open || sheetTitle !== undefined) return

    function handleClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function handleScroll() {
      setOpen(false)
    }

    document.addEventListener("mousedown", handleClick)
    window.addEventListener("scroll", handleScroll, true)
    return () => {
      document.removeEventListener("mousedown", handleClick)
      window.removeEventListener("scroll", handleScroll, true)
    }
  }, [open, sheetTitle])

  // `role="menu"` 對輔助科技宣告了方向鍵操作: 開啟時焦點進到第一個項目。
  useEffect(() => {
    if (!open || sheetTitle !== undefined) return
    listRef.current?.querySelector<HTMLElement>("[role='menuitem']")?.focus()
  }, [open, sheetTitle])

  // 項目多半是打開對話框, 對話框關閉時把焦點還給開啟前的元素: 先還給觸發按鈕, 否則會掉到 body。
  const closeAndRestoreFocus = () => { setOpen(false); triggerRef.current?.focus() }

  function renderItems(itemClassName: string | undefined) {
    return visibleItems.map((item, index) => (
      <button
        key={index}
        type="button"
        role="menuitem"
        className={cls(itemClassName, item.color === "error" && styles.itemError)}
        onClick={() => {
          closeAndRestoreFocus()
          item.onClick()
        }}
      >
        {item.icon && <span className={styles.itemIcon}>{item.icon}</span>}
        {item.label}
      </button>
    ))
  }

  if (visibleItems.length === 0) return null

  return (
    <div ref={ref} className={cls(styles.wrapper, fullWidth && styles.wrapperFull)}>
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName ?? styles.trigger}
        onClick={toggleOpen}
        aria-label={triggerLabel}
        aria-haspopup={sheetTitle === undefined ? "menu" : "dialog"}
        aria-expanded={open}
      >
        {trigger}
      </button>
      {open && sheetTitle === undefined && (
        <div ref={listRef} className={styles.dropdown} role="menu" style={position} onKeyDown={(event) => handleMenuKeyDown(event, closeAndRestoreFocus)}>
          {renderItems(styles.item)}
        </div>
      )}
      {/* 觸發點可能在有 backdrop-filter 的外層 (底部導覽) 裡, 它會變成 fixed 的定位基準, 遮罩就蓋不滿畫面。 */}
      {open && sheetTitle !== undefined && createPortal(
        <Modal title={sheetTitle} open onOpenChange={setOpen}>
          <div className={styles.sheetList} role="menu">
            {renderItems(cls(styles.item, styles.sheetItem))}
          </div>
        </Modal>,
        document.body,
      )}
    </div>
  )
}
