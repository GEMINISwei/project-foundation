import { describe, expect, it } from "vitest"

import {
  validateCreateUserValues, validateEditUserValues, validateResetPassword,
} from "@/modules/users/validation"
import { MIN_PASSWORD_LENGTH } from "@/modules/auth/public.client"

const VALID_PASSWORD = "a".repeat(MIN_PASSWORD_LENGTH)
const SHORT_PASSWORD = "a".repeat(MIN_PASSWORD_LENGTH - 1)

// 錯誤要標在出錯的那一格 (欄位紅框、aria-invalid), 不能只丟一則 toast: toast 幾秒就消失,
// 使用者回到表單時不知道是哪一格。

describe("validateCreateUserValues", () => {
  it("新增使用者時，暱稱與帳號空白的錯誤標在各自的欄位", () => {
    const errors = validateCreateUserValues(
      { username: "  ", nickname: "", password: VALID_PASSWORD },
      "zh",
    )

    expect(errors.username).toBeTruthy()
    expect(errors.nickname).toBeTruthy()
    expect(errors.password).toBeUndefined()
  })

  it("新增使用者時，密碼不符政策的錯誤標在密碼欄位", () => {
    const errors = validateCreateUserValues(
      { username: "new-user", nickname: "New", password: SHORT_PASSWORD },
      "zh",
    )

    expect(errors.password).toBeTruthy()
    expect(errors.username).toBeUndefined()
    expect(errors.nickname).toBeUndefined()
  })
})

describe("validateResetPassword", () => {
  it("重設密碼時，密碼不符政策的錯誤標在密碼欄位", () => {
    expect(validateResetPassword(SHORT_PASSWORD, "zh").password).toBeTruthy()
    expect(validateResetPassword(VALID_PASSWORD, "zh").password).toBeUndefined()
  })
})

describe("validateEditUserValues", () => {
  it("編輯使用者時，暱稱空白的錯誤標在暱稱欄位", () => {
    expect(validateEditUserValues({ nickname: "  " }, "zh").nickname).toBeTruthy()
    expect(validateEditUserValues({ nickname: "New" }, "zh").nickname).toBeUndefined()
  })
})
