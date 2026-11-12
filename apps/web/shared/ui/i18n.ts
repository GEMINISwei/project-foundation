/**
 * UI kit 自己的字串。
 *
 * **刻意不從 `index.ts` 匯出** —— 這是實作細節, 比照 `internals.ts`。kit 以外的地方
 * 需要某段文字時, 請在自己的模組字典裡定義, 不要來這裡取用; 否則 kit 的文案就再也
 * 不能安全調整 (改一個字會影響到不知道在哪裡的畫面)。
 *
 * kit 裡帶文字的元件全部是 client component, 所以一律走 `useT(uiMessages)`。
 */

import { defineMessages } from "@/shared/i18n/dictionary"

export const uiMessages = defineMessages({
  zh: {
    close: "關閉",
    loading: "載入中",
    cancel: "取消",
    pending: "處理中",
    reset: "重置",
    filter: "篩選",
    refresh: "重整",
    actionMenu: "操作選單",
    actionFailed: "操作失敗",
    prevPage: "上一頁",
    nextPage: "下一頁",
    pageOf: "第 {seq} 頁／共 {total} 頁",
    statusActive: "啟用",
    statusDisabled: "停用",
    filterAll: "全部",
    filterActive: "啟用中",
    filterDisabled: "已停用",
  },
  en: {
    close: "Close",
    loading: "Loading",
    cancel: "Cancel",
    pending: "Processing",
    reset: "Reset",
    filter: "Filter",
    refresh: "Refresh",
    actionMenu: "Actions",
    actionFailed: "Action failed",
    prevPage: "Previous",
    nextPage: "Next",
    pageOf: "Page {seq} of {total}",
    statusActive: "Active",
    statusDisabled: "Disabled",
    filterAll: "All",
    filterActive: "Active",
    filterDisabled: "Disabled",
  },
})
