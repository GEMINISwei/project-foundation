/**
 * 字典的型別與查詢。純函式, 不碰 React 也不碰 cookie。
 *
 * 字典本身**不放這裡** —— 各模組的字串住在自己的 `i18n.ts`, UI kit 的住在 `shared/ui/i18n.ts`,
 * 跨模組共用的住在 `config/i18n.ts`。中央字典會違反「`shared/` 不可引用 `modules/`」, 而且
 * 刪掉一個模組就得回頭清理 shared。
 */

import type { Locale } from "./locale"

type Dict = Record<string, string>

/**
 * 一份字典的兩個語系。
 *
 * `en` 標成 `Record<keyof T, string>` (T 由 `zh` 推導): 少一個 key 會編譯失敗, 多一個會被
 * excess property check 擋下。**這是這套方案唯一的品質保證** —— 沒有它, 漏翻譯只會在切到
 * 英文的人手上變成 `undefined`。
 */
export type Messages<T extends Dict = Dict> = { zh: T; en: Record<keyof T, string> }

/** 定義一份字典。存在的理由只有一個: 讓 TypeScript 從 `zh` 推導出 key 的集合。 */
export function defineMessages<const T extends Dict>(messages: Messages<T>): Messages<T> {
  return messages
}

export type Translator<T extends Dict> = (
  key: keyof T,
  values?: Record<string, string | number>,
) => string

/**
 * 產生查字典的函式。插值用 `{name}`: `t("greeting", { name })`。
 *
 * 刻意只支援字串替換, 不做複數與日期格式化 —— 需要那些時再引入正式的 i18n 方案, 不要在這裡
 * 長出半套實作。找不到的佔位符原樣留著, 比替換成空字串容易在畫面上被發現。
 */
export function translate<T extends Dict>(messages: Messages<T>, locale: Locale): Translator<T> {
  const dict = messages[locale] as Record<keyof T, string>

  return (key, values) => {
    const text = dict[key]
    if (!values) return text

    return text.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in values ? String(values[name]) : match
    )
  }
}
