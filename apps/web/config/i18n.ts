/**
 * 組裝層自己的字串: 不屬於任何模組、也不屬於 UI kit 的那些。
 *
 * 應用外殼 (側欄、導覽)、首頁、錯誤頁與 404 都在這裡。模組的字串請放各自的
 * `modules/<name>/i18n.ts` —— 放進來的話, 刪掉那個模組時會留下沒人用的字串。
 */

import { defineMessages } from "@/shared/i18n/dictionary"

export const appMessages = defineMessages({
  zh: {
    // 應用外殼
    mainNav: "主要導覽",
    mobileNav: "手機主要導覽",
    navSection: "導覽",
    navSectionAdmin: "管理功能",
    goAdminArea: "管理後台",
    goUserArea: "使用者畫面",
    accountMenu: "帳號選單",
    account: "帳號",
    accountSettings: "設定",
    adminAreaBadge: "管理後台",
    logout: "登出",
    roleSuperAdmin: "超級管理者",
    roleUser: "使用者",
    // 首頁
    homeTitle: "首頁",
    homeHeading: "歡迎使用",
    homeSubtitle: "請從左側選單選擇功能開始使用。",
    // 404
    notFoundTitle: "找不到頁面",
    notFoundDescription: "這個網址不存在，或是內容已經被移除。",
    backHome: "回首頁",
    // 錯誤頁
    errorTitle: "系統發生錯誤",
    errorDescription: "請重新整理頁面，或聯絡系統管理員。",
    retry: "重新整理",
    // 錯誤畫面的錯誤代碼 (Next 的 digest), 使用者回報時用它查伺服器 log
    errorReference: "錯誤代碼：{digest}",
    // 頁面層的 error boundary (錯誤範圍比 global-error 小, 文案也比較輕)
    pageErrorTitle: "發生錯誤",
    pageErrorDescription: "頁面載入時發生預期外的錯誤，請嘗試重新載入。",
    reload: "重新載入",
  },
  en: {
    mainNav: "Main navigation",
    mobileNav: "Mobile navigation",
    navSection: "Navigation",
    navSectionAdmin: "Management",
    goAdminArea: "Admin",
    goUserArea: "User view",
    accountMenu: "Account menu",
    account: "Account",
    accountSettings: "Settings",
    adminAreaBadge: "Admin",
    logout: "Sign out",
    roleSuperAdmin: "Super admin",
    roleUser: "User",
    homeTitle: "Home",
    homeHeading: "Welcome",
    homeSubtitle: "Pick a feature from the menu to get started.",
    notFoundTitle: "Page not found",
    notFoundDescription: "This address does not exist, or the content has been removed.",
    backHome: "Back to home",
    errorTitle: "Something went wrong",
    errorDescription: "Please refresh the page, or contact your administrator.",
    retry: "Refresh",
    errorReference: "Error code: {digest}",
    pageErrorTitle: "Something went wrong",
    pageErrorDescription: "An unexpected error occurred while loading this page. Please try again.",
    reload: "Reload",
  },
})
