import { SETTINGS_MODULE } from "@/modules/settings/manifest"
import { accessibleRoutes } from "@/config/routes"
import type { appMessages } from "@/config/i18n"
import type { RouteArea } from "@/shared/module"

/** 項目的代號, 同時是 `appMessages` 的字典 key。 */
export type AccountMenuLabel = Extract<
  keyof (typeof appMessages)["zh"],
  "goAdminArea" | "goUserArea" | "accountSettings" | "logout"
>

export type AccountMenuEntry =
  | { kind: "link"; href: string; label: Exclude<AccountMenuLabel, "logout"> }
  | { kind: "logout"; label: "logout" }

const SETTINGS_PATH = SETTINGS_MODULE.protectedRoutes[0].path

/**
 * 頭像選單的項目: 切換區域 (進得去管理區的人才有)、設定、登出。
 *
 * 切換區域放這裡而不是導覽列: 它是換一個情境, 不是開一個頁面, 而且只有超級管理者用得到。
 * 管理區的入口連到「第一個進得去的管理頁」, 與導覽列用同一個 `accessibleRoutes`,
 * 看得到入口就一定進得去。
 */
export function getAccountMenuEntries(
  area: RouteArea,
  permissions: readonly string[],
): AccountMenuEntry[] {
  const firstAdminRoute = accessibleRoutes("admin", permissions)[0]
  const areaSwitch: AccountMenuEntry[] =
    area === "admin"
      ? [{ kind: "link", href: "/", label: "goUserArea" }]
      : firstAdminRoute
        ? [{ kind: "link", href: firstAdminRoute.path, label: "goAdminArea" }]
        : []

  return [
    ...areaSwitch,
    { kind: "link", href: SETTINGS_PATH, label: "accountSettings" },
    { kind: "logout", label: "logout" },
  ]
}
