type ActionFormValue = string | readonly string[] | undefined

/**
 * 帶著欄位型別的 `FormData`。
 *
 * `__fields` 是 phantom type, 執行期不存在 (`FormData` 本身沒有這個屬性), 只用來讓
 * `getActionForm*` 的 name 參數收成 `keyof T`。少了它, 欄位名會變成組裝端與讀取端
 * 各寫一次的字面字串, 打錯字要到執行期拿到空字串才發現 —— 而各模組的 `actions.ts`
 * 正是刻意不寫執行期測試的一層 (見 docs/foundation/testing.md〈前端〉)。
 */
export type ActionFormData<T> = FormData & { readonly __fields?: T }

/**
 * 敏感 Server Action 一律收 FormData, 避免 Next 的 development action log 展開明文欄位。
 * 這不是授權邊界; Server Action 與 API 仍各自驗證輸入。
 */
export function createActionFormData<
  T extends { [K in keyof T]: ActionFormValue },
>(values: T): ActionFormData<T> {
  const data = new FormData()

  for (const [name, value] of Object.entries(values)) {
    if (typeof value === "string") {
      data.append(name, value)
    } else if (Array.isArray(value)) {
      value.forEach((item) => data.append(name, item))
    }
  }

  return data
}

export function getActionFormString<T>(
  data: ActionFormData<T>,
  name: keyof T & string,
): string {
  const value = data.get(name)
  return typeof value === "string" ? value : ""
}

export function getActionFormStrings<T>(
  data: ActionFormData<T>,
  name: keyof T & string,
): string[] {
  return data.getAll(name).filter((value): value is string => typeof value === "string")
}
