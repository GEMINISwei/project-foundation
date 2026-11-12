import type { ReactNode } from "react"
import table from "../styles/table.module.css"
import primitives from "../styles/primitives.module.css"

type ListTableCardProps = {
  headers: string[]
  isEmpty: boolean
  emptyText: string
  children: ReactNode
}

export default function ListTableCard({
  headers,
  isEmpty,
  emptyText,
  children,
}: ListTableCardProps) {
  return (
    <div className={table.tableCard}>
      <table className={`${table.dataTable} ${table.mobileCardTable}`}>
        <thead>
          <tr>
            {headers.map((header) => <th key={header}>{header}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
      {isEmpty && <div className={primitives.emptyState}>{emptyText}</div>}
    </div>
  )
}
