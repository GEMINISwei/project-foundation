"use client"

import { type FormEvent, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "../primitives"
import { Modal } from "../dialogs"
import { SelectInput, TextInput } from "../forms"
import { useT } from "@/shared/i18n/context"
import { uiMessages } from "../i18n"
import styles from "../styles/primitives.module.css"

export type FilterField =
  | { name: string; label: string; type: "text" }
  | { name: string; label: string; type: "select"; options: Array<{ value: string; label: string }> }

/** 「全部/啟用中/已停用」的篩選選項。是 hook 的理由同 `useActiveStatusOptions`。 */
export function useStatusFilterOptions() {
  const t = useT(uiMessages)

  return [
    { value: "", label: t("filterAll") },
    { value: "false", label: t("filterActive") },
    { value: "true", label: t("filterDisabled") },
  ]
}

type FilterDialogProps = {
  title: string
  open: boolean
  onClose: () => void
  fields: FilterField[]
  initialValues: Record<string, string>
}

export default function FilterDialog({
  title,
  open,
  onClose,
  fields,
  initialValues,
}: FilterDialogProps) {
  const t = useT(uiMessages)
  const router = useRouter()
  const pathname = usePathname()
  const [values, setValues] = useState<Record<string, string>>(initialValues)

  function resetFields() {
    setValues(Object.fromEntries(fields.map((field) => [field.name, ""])))
  }

  function setValue(name: string, value: string) {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const params = new URLSearchParams()
    for (const field of fields) {
      const value = values[field.name] ?? ""
      if (field.type === "text") {
        if (value.trim()) params.set(field.name, value.trim())
      } else if (value) {
        params.set(field.name, value)
      }
    }

    const query = params.toString()
    router.push(query ? `${pathname}?${query}` : pathname)
    onClose()
  }

  return (
    <Modal title={title} open={open} onOpenChange={(next) => { if (!next) onClose() }}>
      <form className={styles.dialogForm} onSubmit={submitFilter}>
        {fields.map((field, index) => field.type === "text" ? (
          <TextInput
            key={field.name}
            label={field.label}
            value={values[field.name] ?? ""}
            autoFocus={index === 0}
            onChange={(value) => setValue(field.name, value)}
          />
        ) : (
          <SelectInput
            key={field.name}
            label={field.label}
            value={values[field.name] ?? ""}
            options={field.options}
            onChange={(value) => setValue(field.name, value)}
          />
        ))}
        <div className={styles.dialogFormActions}>
          <Button variant="outlined" type="button" onClick={resetFields}>{t("reset")}</Button>
          <Button type="submit">{t("filter")}</Button>
        </div>
      </form>
    </Modal>
  )
}
