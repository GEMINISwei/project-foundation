import type { ReactNode } from "react"
import styles from "../styles/page-header.module.css"
import ActionMenu, { type ActionMenuItem } from "./ActionMenu"

type PageHeaderProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  mobileActions?: (ActionMenuItem | null | false | undefined)[]
}

export default function PageHeader({ title, subtitle, actions, mobileActions }: PageHeaderProps) {
  return (
    <header className={styles.pageHeader}>
      <div className={styles.pageHeaderText}>
        <h1 className={styles.pageTitle}>{title}</h1>
        {subtitle && <p className={styles.pageSubtitle}>{subtitle}</p>}
      </div>
      {actions && <div className={styles.pageHeaderActions}>{actions}</div>}
      {mobileActions && (
        <div className={styles.pageHeaderMobileActions}>
          <ActionMenu items={mobileActions} />
        </div>
      )}
    </header>
  )
}
