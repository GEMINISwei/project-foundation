// 角色在畫面上的名稱規則。權限的標籤與分類不在這裡: 由後端提供 (見 capabilities.ts 的
// `groupPermissionOptions`)。
import type { Translator } from "@/shared/i18n/dictionary"
import type { rolesMessages } from "./i18n"
import type { RoleInfo } from "./types"

/**
 * 系統角色的顯示名稱。key 是後端 `modules/roles/model.py` 的 role code。
 *
 * 角色名存在 DB 裡而且使用者可以改, 所以它是資料不是文案, 做成雙語會污染資料模型。但 seed 出來
 * 的系統角色是**模板給的**, 英文使用者不該看到「超級管理者」, 所以在顯示這一層依 code 換掉。
 *
 * 刻意**不做窮盡檢查**: 後端沒有 role code 的 enum, 下游也可以自己 seed 更多系統角色。
 * 認不出的 code 退回 DB 名稱是安全的降級。
 */
const SYSTEM_ROLE_NAME_KEYS = {
  super_admin: "roleSuperAdmin",
} as const satisfies Record<string, keyof (typeof rolesMessages)["zh"]>

/**
 * 角色在畫面上的名稱。系統角色走字典, 其他角色用 DB 名稱。這個模組是唯一擁有者, users 模組經
 * `public.client.ts` 取用 —— 兩邊各寫一份的話, 改了顯示規則只會有一邊跟上。
 */
export function getRoleDisplayName(
  role: Pick<RoleInfo, "code" | "name">,
  t: Translator<(typeof rolesMessages)["zh"]>,
): string {
  const key = role.code
    ? SYSTEM_ROLE_NAME_KEYS[role.code as keyof typeof SYSTEM_ROLE_NAME_KEYS]
    : undefined

  return key ? t(key) : role.name
}
