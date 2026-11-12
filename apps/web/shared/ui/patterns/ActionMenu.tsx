"use client"

import { MoreVertical } from "lucide-react"
import { useT } from "@/shared/i18n/context"
import { uiMessages } from "../i18n"
import { ICON_SIZE } from "../internals"
import Menu, { type MenuItem } from "./Menu"

export type ActionMenuItem = MenuItem

type ActionMenuProps = {
  items: (ActionMenuItem | null | false | undefined)[]
}

/** 表格列尾的「⋮」操作選單。 */
export default function ActionMenu({ items }: ActionMenuProps) {
  const t = useT(uiMessages)

  return (
    <Menu
      items={items}
      trigger={<MoreVertical size={ICON_SIZE.sm} />}
      triggerLabel={t("actionMenu")}
    />
  )
}
