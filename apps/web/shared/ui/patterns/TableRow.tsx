import type { ReactNode } from "react"
import table from "../styles/table.module.css"

type TableRowProps = {
  children: ReactNode
}

/**
 * `ListTableCard` 的資料列。
 *
 * 存在的理由只有一個: 讓「窄螢幕時把 table 轉成卡片」所需的 class 留在 UI kit 內部。
 * 少了它, 每個模組的列表畫面都得自己 import `styles/table.module.css`,
 * shared/ui 的樣式就變成了公開介面, 之後任何調整都會牽動所有模組。
 */
export default function TableRow({ children }: TableRowProps) {
  return <tr className={table.mobileCardRow}>{children}</tr>
}
