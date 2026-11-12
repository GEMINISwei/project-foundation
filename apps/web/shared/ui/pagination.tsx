"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight } from "lucide-react"
import type { PageMeta } from "@/shared/api/types"
import { useT } from "@/shared/i18n/context"
import { ICON_SIZE } from "./internals"
import styles from "./styles/primitives.module.css"
import { cls } from "./internals"
import { uiMessages } from "./i18n"
import { Flex } from "./primitives"

type PaginationProps = { meta: PageMeta; seq: number; limit: number; summary?: ReactNode }

export function usePaginationResetHref(): string {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const params = new URLSearchParams(searchParams.toString())
  params.delete("cursor")
  params.delete("direction")
  params.delete("seq")
  const query = params.toString()
  return query ? `${pathname}?${query}` : pathname
}

export function Pagination({ meta, seq, limit, summary }: PaginationProps) {
  const t = useT(uiMessages)
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const totalPages =
    Math.max(1, Math.ceil(meta.total / limit))
  // 保留現有的篩選條件, 只換掉游標三件組; 一定帶 cursor, 所以網址一定有 `?`。
  function hrefFor(direction: "next" | "prev", cursor: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("cursor", cursor)
    params.set("direction", direction)
    params.set("seq", String(direction === "next" ? seq + 1 : seq - 1))
    return `${pathname}?${params.toString()}`
  }
  return (
    <div className={styles.paginationBar}>
      <Flex gap={2} className={styles.paginationButtons}>
        {meta.prevCursor ? (
          <Link href={hrefFor("prev", meta.prevCursor)} className={styles.paginationLink}>
            <ChevronLeft size={ICON_SIZE.sm} aria-hidden="true" /> {t("prevPage")}
          </Link>
        ) : (
          <span className={cls(styles.paginationLink, styles.paginationLinkDisabled)} aria-disabled="true">
            <ChevronLeft size={ICON_SIZE.sm} aria-hidden="true" /> {t("prevPage")}
          </span>
        )}
        {meta.nextCursor ? (
          <Link href={hrefFor("next", meta.nextCursor)} className={styles.paginationLink}>
            {t("nextPage")} <ChevronRight size={ICON_SIZE.sm} aria-hidden="true" />
          </Link>
        ) : (
          <span className={cls(styles.paginationLink, styles.paginationLinkDisabled)} aria-disabled="true">
            {t("nextPage")} <ChevronRight size={ICON_SIZE.sm} aria-hidden="true" />
          </span>
        )}
      </Flex>
      <div className={styles.paginationSummary}>
        <span className={styles.paginationCurrent}>
          {t("pageOf", { seq, total: totalPages })}
          {summary && ` (${summary})`}
        </span>
      </div>
    </div>
  )
}
