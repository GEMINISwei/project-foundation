// UI kit 的內部工具; 版面元件直接使用 `as`、`className` 與 `style`。

/** 鍵盤可以聚焦到的元素; 對話框的焦點循環用它找出第一個與最後一個。 */
export const FOCUSABLE_SELECTOR = [
  "a[href]", "button:not([disabled])", "input:not([disabled])", "select:not([disabled])",
  "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])",
].join(", ")

/**
 * 觸控為主的裝置 (手機、平板)。這類裝置上不自動聚焦輸入框: 焦點一進去就跳出鍵盤,
 * WebApp 要像原生 App 一樣, 使用者點了欄位才輸入。沒有 `matchMedia` 的環境 (伺服器端) 當成不是。
 */
export function isCoarsePointer() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(pointer: coarse)").matches
}

export function cls(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ")
}

/** 版面元件共用的基本 props: 換 HTML 標籤、加 class、加行內樣式。 */
export type BaseProps = {
  /** 要渲染成哪個 HTML 標籤, 預設由各元件決定。例: `<Container as="section">`。 */
  as?: React.ElementType
  className?: string
  style?: React.CSSProperties
}

/**
 * 間距刻度的階號。刻意是聯集而不是 `number`: 階號不是倍率, 而是 `shared/ui/styles/tokens.css` 裡真的
 * 存在的那幾個 token。收成 `number` 的話 `gap={7}` 會產生不存在的 `var(--space-7)`,
 * gap 靜靜變成 0。
 */
export type SpaceStep = 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12

/**
 * 間距: 階號換成對應的 token, 字串原樣輸出。
 *
 * 回傳 `var(--space-n)` 而不是自己算 px —— 刻度的單一事實來源留在 CSS 那一側
 * (`shared/ui/styles/tokens.css` 的 `--space-*`)。在這裡算 px 的話, 改刻度要同時改兩邊。
 */
export function spacing(value: SpaceStep | string | undefined) {
  if (value === undefined) return undefined
  return typeof value === "number" ? `var(--space-${value})` : value
}

/**
 * 圖示尺寸。lucide 的 `size` prop 產生 `<svg width height>`, CSS 的 `--size-icon-*` 管不到它,
 * 所以刻度在這裡再宣告一份, **數字必須與 `shared/ui/styles/tokens.css` 的 `--size-icon-*` 相同**。
 *
 * 尺寸會隨斷點變的圖示 (側欄與底部導覽) 不要用這個 —— media query 改得動 CSS, 改不動 prop。
 */
export const ICON_SIZE = { sm: 16, md: 20, lg: 24 } as const
