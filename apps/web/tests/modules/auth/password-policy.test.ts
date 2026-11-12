import { describe, expect, it } from "vitest"
import { MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH, validateLoginPassword, validateNewPassword } from "@/modules/auth/password-policy"
import { authMessages } from "@/modules/auth/i18n"

describe("validateNewPassword", () => {
  it("空值要求輸入", () => {
    expect(validateNewPassword("", "zh")).toBe(authMessages.zh.passwordRequired)
  })

  it("長度以「字元數」計算，剛好達標即通過", () => {
    expect(validateNewPassword("a".repeat(MIN_PASSWORD_LENGTH - 1), "zh")).toBeDefined()
    expect(validateNewPassword("a".repeat(MIN_PASSWORD_LENGTH), "zh")).toBeUndefined()
  })

  it("中文密碼以字元數計長度，不會因為位元組較多而被誤判太短", () => {
    // 8 個中文字 = 8 字元但 24 bytes。長度檢查看的是字元數, 所以應該通過。
    expect(validateNewPassword("密碼密碼密碼密碼", "zh")).toBeUndefined()
  })

  it("上限以「位元組」計算 —— 這是 bcrypt 的硬限制", () => {
    expect(validateNewPassword("a".repeat(MAX_PASSWORD_BYTES), "zh")).toBeUndefined()
    expect(validateNewPassword("a".repeat(MAX_PASSWORD_BYTES + 1), "zh")).toBeDefined()
  })

  it("24 個中文字剛好 72 bytes，第 25 個就超過", () => {
    // 這正是字元數與位元組數必須分開檢查的原因, 也是最容易寫錯的邊界。
    expect("密".repeat(24).length).toBe(24)
    expect(new TextEncoder().encode("密".repeat(24)).length).toBe(MAX_PASSWORD_BYTES)

    expect(validateNewPassword("密".repeat(24), "zh")).toBeUndefined()
    expect(validateNewPassword("密".repeat(25), "zh")).toBeDefined()
  })
})

describe("語系", () => {
  it("錯誤訊息跟著語系走", () => {
    expect(validateNewPassword("", "en")).toBe(authMessages.en.passwordRequired)
  })

  it("長度限制會代入實際數字，不是寫死在字典裡", () => {
    expect(validateNewPassword("a", "en")).toContain(String(MIN_PASSWORD_LENGTH))
    expect(validateNewPassword("a".repeat(MAX_PASSWORD_BYTES + 1), "en")).toContain(String(MAX_PASSWORD_BYTES))
  })
})

describe("validateLoginPassword", () => {
  it("登入時不檢查長度下限 —— 舊帳號的短密碼仍要能登入", () => {
    expect(validateLoginPassword("short", "zh")).toBeUndefined()
  })

  it("但仍檢查位元組上限", () => {
    expect(validateLoginPassword("a".repeat(MAX_PASSWORD_BYTES + 1), "zh")).toBeDefined()
  })

  it("空值仍要求輸入", () => {
    expect(validateLoginPassword("", "zh")).toBe(authMessages.zh.passwordRequired)
  })
})
