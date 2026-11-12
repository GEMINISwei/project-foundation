// 表單元件一律使用具名 props, 避免同一個值有多個設定入口。
"use client"

import type * as React from "react"
import type { HTMLInputTypeAttribute, ReactNode } from "react"
import { useId } from "react"
import { ChevronDown } from "lucide-react"
import { useT } from "@/shared/i18n/context"
import { cls, ICON_SIZE, isCoarsePointer } from "./internals"
import styles from "./styles/primitives.module.css"
import { uiMessages } from "./i18n"

type TextInputProps = {
  id?: string
  name?: string
  label?: string
  value?: string | number
  type?: HTMLInputTypeAttribute
  required?: boolean
  disabled?: boolean
  placeholder?: string
  autoComplete?: string
  autoFocus?: boolean
  error?: string
  /** 可見標籤在別處時用 (例如登入頁只有 placeholder), 此時不要再給 `label`。 */
  ariaLabel?: string
  /** 輸入框左側的圖示。給了之後左內距會讓出空間。 */
  icon?: ReactNode
  /** 輸入框右側的附加控制項 (例如密碼顯示切換)。給了之後右內距會讓出空間。 */
  trailing?: ReactNode
  /** lg 給登入這類刻意放大的表單; 預設 md。 */
  size?: "md" | "lg"
  onChange?: (value: string) => void
}

/** 欄位標籤; 必填時補上星號。 */
function FieldLabel({ label, required }: { label?: string; required?: boolean }) {
  if (!label) return null
  return (
    <span className={styles.label}>
      {label}
      {required && <span className={styles.requiredMark}>*</span>}
    </span>
  )
}

function FieldError({ id, error }: { id?: string; error?: string }) {
  if (!error) return null
  return <span id={id} className={styles.fieldError} role="alert">{error}</span>
}

/** 前置圖示與尾端控制項的版面; 兩者都沒有時不多包一層 DOM。 */
function AdornedInput({ icon, trailing, className, children }: {
  icon?: ReactNode
  trailing?: ReactNode
  className: string
  children: ReactNode
}) {
  if (!icon && !trailing) return children
  return (
    <span className={className}>
      {icon && <span className={styles.inputIcon}>{icon}</span>}
      {children}
      {trailing && <span className={styles.inputTrailing}>{trailing}</span>}
    </span>
  )
}

export function TextInput({
  id,
  name,
  label,
  error,
  ariaLabel,
  icon,
  trailing,
  size = "md",
  ...props
}: TextInputProps) {
  // id 一律由 useId 產生, **不要退回用 name**: 同一頁出現兩個同名欄位時 name 會產生
  // 重複的 DOM id, `aria-describedby` 指到哪一個是未定義的。label 已經包住輸入框,
  // id 存在的唯一理由就是把錯誤訊息接上去。
  const generatedId = useId()
  const inputId = id ?? generatedId
  const errorId = error ? `${inputId}-error` : undefined
  const { onChange, autoFocus, ...inputProps } = props
  const accessibility = {
    id: inputId,
    name,
    "aria-label": ariaLabel,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": errorId,
  }

  return (
    <label className={styles.field}>
      <FieldLabel label={label} required={inputProps.required} />
      <AdornedInput icon={icon} trailing={trailing} className={styles.inputAdorned}>
        <input
          className={cls(
            styles.input,
            size === "lg" && styles.inputLg,
            icon ? styles.inputWithIcon : undefined,
            trailing ? styles.inputWithTrailing : undefined,
            error && styles.inputError,
          )}
          onChange={(event) => onChange?.(event.target.value)}
          autoFocus={autoFocus && !isCoarsePointer()}
          {...accessibility}
          {...inputProps}
        />
      </AdornedInput>
      <FieldError id={errorId} error={error} />
    </label>
  )
}

/**
 * 啟用/停用的下拉選項。
 *
 * 是 hook 而不是常數陣列: label 要跟著語系走, 而模組載入時還沒有語系。
 * 所有消費端都是 client component, 所以 hook 這個形式沒有增加限制。
 */
export function useActiveStatusOptions() {
  const t = useT(uiMessages)

  return [
    { value: "active", label: t("statusActive") },
    { value: "disabled", label: t("statusDisabled") },
  ] as const
}

type SelectInputProps = {
  id?: string
  name?: string
  label?: string
  value?: string
  required?: boolean
  disabled?: boolean
  options: ReadonlyArray<{ label?: string; text?: string; value: string }>
  autoFocus?: boolean
  error?: string
  /** 可見標籤在別處時用 (例如設定頁的列名), 此時不要再給 `label`。 */
  ariaLabel?: string
  onChange?: (value: string) => void
}

export function SelectInput({
  id, name, label, options, error, ariaLabel, ...props
}: SelectInputProps) {
  // id 的產生方式與 TextInput 一致, 理由見那裡。
  const generatedId = useId()
  const inputId = id ?? generatedId
  const errorId = error ? `${inputId}-error` : undefined
  const { onChange, autoFocus, ...selectProps } = props
  return (
    <label className={styles.field}>
      <FieldLabel label={label} required={selectProps.required} />
      <span className={styles.selectControl}>
        <select
          className={styles.select}
          id={inputId}
          name={name}
          aria-label={ariaLabel}
          aria-invalid={error ? true : undefined}
          aria-describedby={errorId}
          onChange={(event) => onChange?.(event.target.value)}
          autoFocus={autoFocus && !isCoarsePointer()}
          {...selectProps}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>{option.label ?? option.text}</option>
          ))}
        </select>
        <ChevronDown className={styles.selectIndicator} size={ICON_SIZE.sm} aria-hidden="true" />
      </span>
      <FieldError id={errorId} error={error} />
    </label>
  )
}

type FormProps = {
  id?: string
  children: React.ReactNode
  onSubmit?: (event: React.FormEvent<HTMLFormElement>) => void
}

// 整頁表單的容器, 欄位間距與 `FormDialog` 內部那個 form 一致。
// `id` 是給 `FormPageShell` 的送出鈕用 `form="<id>"` 從表單外部觸發的。
export function Form({ id, children, onSubmit }: FormProps) {
  return (
    <form id={id} className={styles.dialogForm} onSubmit={onSubmit}>
      {children}
    </form>
  )
}
