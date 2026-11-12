import type { ReactNode } from "react"
import styles from "../styles/primitives.module.css"

type ErrorStateProps = {
  children: ReactNode
}

// 列表/區塊層級的錯誤訊息。存在的理由是邊界: 沒有它, 每個模組都會去
// `composes: errorState from "../../../shared/ui/styles/primitives.module.css"`,
// 而 CSS 檔之間的 `composes:` 不在 dependency-cruiser 的射程內, 那條外洩不會有紅燈。
// 沒有 "use client": 純顯示, 兩邊都能用。
export default function ErrorState({ children }: ErrorStateProps) {
  return <div className={styles.errorState}>{children}</div>
}
