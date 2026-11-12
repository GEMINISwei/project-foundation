// 這個模組的使用者可見字串。模組內以相對路徑引用 (`../i18n`、`./i18n`),
// 不從 public entry 匯出 —— 文案是模組的內部細節, 跨模組沒有共用它的理由
// (密碼規則的錯誤訊息也是: 別的模組呼叫 `validateNewPassword()` 拿到的是翻好的字串)。

import { defineMessages } from "@/shared/i18n/dictionary"

export const authMessages = defineMessages({
  zh: {
    loginTitle: "登入帳號",
    login: "登入",
    loggingIn: "登入中",
    username: "帳號",
    password: "密碼",
    showPassword: "顯示密碼",
    hidePassword: "隱藏密碼",
    securityNote: "安全登入 · 資料加密保護",
    usernameRequired: "請輸入帳號",
    loginFailed: "登入失敗",
    sessionExpired: "登入狀態已過期，請重新登入後再繼續操作",
    passwordRequired: "請輸入密碼",
    passwordTooShort: "至少 {min} 個字元",
    passwordTooLong: "不可超過 {max} bytes",
    currentUserFailed: "無法取得目前使用者資訊",
  },
  en: {
    loginTitle: "Sign in",
    login: "Sign in",
    loggingIn: "Signing in",
    username: "Username",
    password: "Password",
    showPassword: "Show password",
    hidePassword: "Hide password",
    securityNote: "Secure sign-in · Encrypted connection",
    usernameRequired: "Username is required",
    loginFailed: "Sign-in failed",
    sessionExpired: "Your session has expired. Please sign in again.",
    passwordRequired: "Password is required",
    passwordTooShort: "At least {min} characters",
    passwordTooLong: "Must not exceed {max} bytes",
    currentUserFailed: "Failed to load the current user",
  },
})
