/**
 * 版面與基本元件。
 *
 * **這個檔案刻意沒有 `"use client"`。** 這些元件沒有 state、effect 或瀏覽器 API, 所以兩邊都能
 * 用: 被 Server Component 引用時就在伺服器算完, 被 client component 引用時才進 client bundle。
 *
 * **要加 state 或事件時請另開檔案**, 不要在這裡加 `"use client"` —— 那會一次把所有版面元件都
 * 拖進 client (`dialogs.tsx`、`notifications.tsx` 就是這樣分出去的)。
 */

import type { CSSProperties, ReactNode } from "react"
import styles from "./styles/primitives.module.css"
import { cls, spacing, type BaseProps, type SpaceStep } from "./internals"

/** 只把有值的自訂屬性放進 style, 沒帶的 prop 交給 CSS 的預設值。 */
function cssVars(vars: Record<string, string | number | undefined>, style?: CSSProperties) {
  const defined = Object.entries(vars).filter(([, value]) => value !== undefined)
  if (defined.length === 0) return style
  return { ...Object.fromEntries(defined), ...style } as CSSProperties
}

/**
 * variant → class 一律寫成 `Record<聯集, string>`, 不要用 `variant === "x" && styles.x` 的布林串:
 * Record 讓 `tsc` 擋下漏掉的 variant, 布林串漏一項則是靜靜沒有效果。
 */
type ButtonVariant = "contained" | "outlined"
type ContainerSize = "sm" | "md" | "lg"

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  contained: styles.buttonContained,
  outlined: styles.buttonOutlined,
}

// md 是預設寬度, 沒有額外的 class —— 空字串是「刻意沒有」, 和漏寫 (undefined) 不同。
const CONTAINER_SIZE: Record<ContainerSize, string> = {
  sm: styles.containerSm,
  md: "",
  lg: styles.containerLg,
}

type FlexProps = BaseProps & {
  children?: ReactNode
  direction?: "row" | "column"
  gap?: SpaceStep | string
  align?: CSSProperties["alignItems"] | "end"
  justify?: CSSProperties["justifyContent"]
}

export function Flex({
  children,
  direction = "row",
  gap,
  align,
  justify,
  as: Component = "div",
  className,
  style,
}: FlexProps) {
  return (
    <Component
      className={cls(styles.flex, className)}
      style={cssVars(
        {
          "--flex-direction": direction,
          "--flex-gap": spacing(gap),
          // 舊瀏覽器只接受 flex-end, 對外仍使用一致的 end API。
          "--flex-align": align === "end" ? "flex-end" : align,
          "--flex-justify": justify,
        },
        style,
      )}
    >
      {children}
    </Component>
  )
}

type ContainerProps = BaseProps & {
  children?: ReactNode
  size?: ContainerSize
  padded?: boolean
}

export function Container({
  children,
  size = "md",
  padded,
  as: Component = "div",
  className,
  style,
}: ContainerProps) {
  return (
    <Component
      className={cls(
        styles.container,
        CONTAINER_SIZE[size],
        padded && styles.containerPadded,
        className,
      )}
      style={style}
    >
      {children}
    </Component>
  )
}

type ButtonProps = BaseProps & {
  children?: ReactNode
  icon?: ReactNode
  type?: "button" | "submit" | "reset"
  variant?: ButtonVariant
  size?: "large"
  fullWidth?: boolean
  disabled?: boolean
  onClick?: () => void
  form?: string
}

export function Button({
  children,
  icon,
  type = "button",
  variant = "contained",
  size,
  fullWidth,
  disabled,
  onClick,
  form,
  as: Component = "button",
  className,
  style,
}: ButtonProps) {
  return (
    <Component
      type={Component === "button" ? type : undefined}
      form={form}
      className={cls(
        styles.button,
        BUTTON_VARIANT[variant],
        size === "large" && styles.buttonLarge,
        fullWidth && styles.buttonFullWidth,
        className,
      )}
      disabled={disabled}
      onClick={onClick}
      style={style}
    >
      {icon}
      {children}
    </Component>
  )
}

type SurfaceProps = BaseProps & { children?: ReactNode }

export function Surface({ children, as: Component = "div", className, style }: SurfaceProps) {
  return <Component className={cls(styles.surface, className)} style={style}>{children}</Component>
}
