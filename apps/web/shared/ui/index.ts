/**
 * UI kit 的**唯一**公開面。`shared/ui/` 以外的檔案一律 `import { X } from "@/shared/ui"`,
 * 不可指進子路徑 —— `internals.ts` 與 `styles/**` 是實作細節 (由 dependency-cruiser 檢查)。
 *
 * **不要把帶 `server-only` 的模組放進 shared/ui**: 這個 barrel 同時被 Server Component 與
 * client component 引用, 只要有一個檔案帶了 `server-only`, 所有 client 端的引用都會在建置時
 * 炸掉。需要 server 能力的東西請放 `shared/api`、`shared/session`。
 *
 * 版面樣板是 default export, 這裡一律轉成具名 —— 呼叫端只要記住一個路徑與一組名字。
 */

// ---- 基本元件 ----
export { Form, SelectInput, TextInput, useActiveStatusOptions } from "./forms"
export { Button, Container, Flex, Surface } from "./primitives"
export { ICON_SIZE } from "./internals"
export { FormDialog, Modal } from "./dialogs"
export { Loading, Notify, NotifyViewport, type NotifyProps } from "./notifications"
export { Pagination, usePaginationResetHref } from "./pagination"

// ---- 版面樣板 ----
export { default as ActionMenu } from "./patterns/ActionMenu"
export { default as FilterDialog, useStatusFilterOptions } from "./patterns/FilterDialog"
export { default as FormPageShell } from "./patterns/FormPageShell"
export { default as ListPageHeader } from "./patterns/ListPageHeader"
export { default as ListTableCard } from "./patterns/ListTableCard"
export { default as Menu, type MenuItem } from "./patterns/Menu"
export { default as PageHeader } from "./patterns/PageHeader"
export { default as StatusBadge } from "./patterns/StatusBadge"
export { default as TableRow } from "./patterns/TableRow"

// ---- 整頁狀態 ----
export { default as ErrorState } from "./feedback/ErrorState"
export { MessagePage, MessagePageButton, MessagePageLink } from "./feedback/MessagePage"
export { default as RouteLoading } from "./feedback/RouteLoading"

// ---- 共用 hook ----
export { useActionSubmit } from "./hooks/useActionSubmit"
export { useListFeedback } from "./hooks/useListFeedback"
export { useNotify } from "./hooks/useNotify"
