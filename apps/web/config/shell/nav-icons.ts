import { Settings, ShieldCheck, Users, type LucideIcon } from "lucide-react"
import type { NavIconKey } from "@/config/routes"

/**
 * 導覽圖示代號 → 實際圖示。manifest 只帶 `navIcon` 字串, 因為它要保持 edge-safe,
 * 不能把 React 元件帶進 middleware 會載入的 `routes.ts`。
 *
 * `Record<NavIconKey, …>` 是窮盡的: 代號打錯或留下已移除模組的條目都會**編譯失敗**。
 */
export const NAV_ICONS: Record<NavIconKey, LucideIcon> = {
  users: Users,
  roles: ShieldCheck,
  settings: Settings,
}
