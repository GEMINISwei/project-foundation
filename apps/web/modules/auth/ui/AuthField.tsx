"use client"

import type { ReactNode } from "react"
import { Eye, EyeOff } from "lucide-react"
import { ICON_SIZE } from "@/shared/ui"
import { TextInput } from "@/shared/ui"
import styles from "./auth.module.css"

type AuthFieldProps = {
  icon: ReactNode
  /** 同時當作 `id` 與 `name`: 登入頁的每個欄位都是這樣, 分開兩個 prop 只會多一個出錯的機會。 */
  name: string
  type: string
  autoComplete: string
  placeholder: string
  /** 省略時沿用 `placeholder`: 多數欄位兩者本來就一樣, 只有提示文與欄位名不同時才要給。 */
  ariaLabel?: string
  value: string
  disabled: boolean
  /** 該欄位目前的驗證訊息。是否真的標紅由 `showError` 決定 —— 送出前不要先罵人。 */
  error?: string
  showError: boolean
  onChange: (value: string) => void
  /** 尾端的附加按鈕 (目前只有密碼的顯示切換)。有值時輸入框會讓出右側空間。 */
  trailing?: ReactNode
}

/**
 * 登入頁的輸入框。
 *
 * 只是 kit `TextInput` 的薄包裝 —— 樣式全部來自 kit, 這裡只多做一件事:
 * `showError` 為假時不把 `error` 往下傳 (送出前不要先罵人)。
 * **不要在這裡另刻樣式**: 那會讓「輸入框長什麼樣」變成兩個地方定義,
 * Design System 換一次就要改兩處而且沒有檢查器會提醒漏了哪處。
 */
export default function AuthField({
  icon,
  name,
  type,
  autoComplete,
  placeholder,
  ariaLabel,
  value,
  disabled,
  error,
  showError,
  onChange,
  trailing,
}: AuthFieldProps) {
  return (
    <TextInput
      icon={icon}
      trailing={trailing}
      size="lg"
      id={name}
      name={name}
      type={type}
      autoComplete={autoComplete}
      placeholder={placeholder}
      ariaLabel={ariaLabel ?? placeholder}
      value={value}
      disabled={disabled}
      error={showError ? error : undefined}
      onChange={onChange}
    />
  )
}

type PasswordToggleProps = {
  visible: boolean
  showLabel: string
  hideLabel: string
  onToggle: () => void
}

/**
 * 登入/註冊表單頂端的錯誤橫幅。
 *
 * 用 `role="alert"` 而不是只給紅字: 登入失敗時螢幕閱讀器要當場念出來,
 * 而使用者的焦點這時仍停在輸入框上。
 */
export function AuthErrorBanner({ open, message }: { open: boolean; message: string }) {
  if (!open) return null

  return (
    <div className={styles.errorBanner} role="alert">
      {message}
    </div>
  )
}

/** 密碼欄位的顯示/隱藏切換。`tabIndex={-1}` 讓 Tab 直接從密碼跳到送出鈕。 */
export function PasswordToggle({ visible, showLabel, hideLabel, onToggle }: PasswordToggleProps) {
  return (
    <button
      type="button"
      aria-label={visible ? hideLabel : showLabel}
      className={styles.inputTrailingBtn}
      onClick={onToggle}
      tabIndex={-1}
    >
      {visible ? <EyeOff size={ICON_SIZE.md} /> : <Eye size={ICON_SIZE.md} />}
    </button>
  )
}
