import type { AssignablePermission, PermissionOption, RoleInfo } from "./types"

/** 系統角色 (有 code) 由初始資料擁有, 後台不能改。 */
export function canManageRole(role: RoleInfo) {
  return role.code === null
}

export type PermissionGroup = {
  category: string
  options: PermissionOption[]
}

/** 依分類分組, 保留後端給的順序。 */
export function groupPermissionOptions(options: readonly PermissionOption[]): PermissionGroup[] {
  const groups = new Map<string, PermissionOption[]>()
  for (const option of options) {
    groups.set(option.category, [...(groups.get(option.category) ?? []), option])
  }
  return [...groups].map(([category, grouped]) => ({ category, options: grouped }))
}

/**
 * 勾選或取消一個權限之後的結果, 連動處理相依關係 (後端儲存時也會強制同一條規則):
 * 勾選時一併勾上它需要的權限; 取消時一併取消需要它的權限。
 */
export function togglePermission(
  selected: readonly AssignablePermission[],
  target: AssignablePermission,
  options: readonly PermissionOption[],
): AssignablePermission[] {
  const requires = new Map(
    options.map((option) => [option.value, option.requires as AssignablePermission[]]),
  )
  const next = new Set(selected)
  const pending = [target]
  if (next.has(target)) {
    while (pending.length > 0) {
      const item = pending.pop()!
      next.delete(item)
      for (const other of next) {
        if (requires.get(other)?.includes(item)) pending.push(other)
      }
    }
  } else {
    while (pending.length > 0) {
      const item = pending.pop()!
      if (next.has(item)) continue
      next.add(item)
      pending.push(...(requires.get(item) ?? []))
    }
  }
  return options
    .map((option) => option.value as AssignablePermission)
    .filter((value) => next.has(value))
}
