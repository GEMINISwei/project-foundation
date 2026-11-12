"use client"

import { useEffect, useId, useRef, useSyncExternalStore } from "react"
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react"
import { useT } from "@/shared/i18n/context"
import { ICON_SIZE } from "./internals"
import styles from "./styles/primitives.module.css"
import { cls } from "./internals"
import { uiMessages } from "./i18n"
import { Flex } from "./primitives"

export type NotifyProps = {
  open: boolean
  message: string
  severity?: "success" | "error" | "info" | "warning"
  duration?: number
  onOpenChange?: (open: boolean) => void
}

type NotifyEntry = {
  id: string
  message: string
  severity: NonNullable<NotifyProps["severity"]>
  close: () => void
}

let notifyEntries: NotifyEntry[] = []
const notifyListeners = new Set<() => void>()
const EMPTY_NOTIFY_ENTRIES: NotifyEntry[] = []

function emitNotifyChange() { notifyListeners.forEach((listener) => listener()) }
function upsertNotify(entry: NotifyEntry) {
  const index = notifyEntries.findIndex((item) => item.id === entry.id)
  notifyEntries = index === -1
    ? [...notifyEntries, entry]
    : notifyEntries.map((item) => item.id === entry.id ? entry : item)
  emitNotifyChange()
}
function removeNotify(id: string) {
  const nextEntries = notifyEntries.filter((entry) => entry.id !== id)
  if (nextEntries.length === notifyEntries.length) return
  notifyEntries = nextEntries
  emitNotifyChange()
}
function subscribeNotify(listener: () => void) {
  notifyListeners.add(listener)
  return () => notifyListeners.delete(listener)
}

const NOTIFY_ICONS: Record<NonNullable<NotifyProps["severity"]>, React.ReactNode> = {
  success: <CheckCircle2 size={ICON_SIZE.sm} aria-hidden="true" />,
  error: <XCircle size={ICON_SIZE.sm} aria-hidden="true" />,
  info: <Info size={ICON_SIZE.sm} aria-hidden="true" />,
  warning: <AlertTriangle size={ICON_SIZE.sm} aria-hidden="true" />,
}
const NOTIFY_SEVERITY_CLASS: Record<NonNullable<NotifyProps["severity"]>, string | undefined> = {
  success: styles.notifySuccess,
  error: styles.notifyError,
  info: styles.notifyInfo,
  warning: styles.notifyWarning,
}

export function Notify({ open, message, severity = "info", duration, onOpenChange }: NotifyProps) {
  const id = useId()
  const onOpenChangeRef = useRef(onOpenChange)
  useEffect(() => { onOpenChangeRef.current = onOpenChange }, [onOpenChange])
  useEffect(() => {
    if (!open) { removeNotify(id); return }
    upsertNotify({ id, message, severity, close: () => onOpenChangeRef.current?.(false) })
  }, [id, message, open, severity])
  useEffect(() => () => removeNotify(id), [id])
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(() => onOpenChangeRef.current?.(false), duration ?? 5000)
    return () => clearTimeout(timer)
  }, [open, duration])
  return null
}

export function NotifyViewport() {
  const t = useT(uiMessages)
  const entries = useSyncExternalStore(
    subscribeNotify,
    () => notifyEntries,
    () => EMPTY_NOTIFY_ENTRIES,
  )
  if (entries.length === 0) return null
  return (
    <div className={styles.notifyViewport} aria-live="assertive">
      {entries.map((entry) => (
        <div key={entry.id} role="alert" className={cls(styles.notify, NOTIFY_SEVERITY_CLASS[entry.severity])}>
          <span className={styles.notifyIcon}>{NOTIFY_ICONS[entry.severity]}</span>
          <span className={styles.notifyMessage}>{entry.message}</span>
          <button type="button" className={styles.notifyClose} aria-label={t("close")} onClick={entry.close}>
            <X size={ICON_SIZE.sm} aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  )
}

// text 預設值走字典而不是參數預設值: 參數預設值是在模組載入時求值的, 那時還沒有語系。
export function Loading({ text }: { text?: string }) {
  const t = useT(uiMessages)
  return (
    <div className={styles.loading}>
      <Flex align="center" gap={2}>
        <span className={styles.spinner} />
        <span>{text ?? t("loading")}</span>
      </Flex>
    </div>
  )
}
