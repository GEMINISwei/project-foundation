import { describe, expect, it } from "vitest"

import { validateNickname, validatePasswordValues } from "@/modules/settings/validation"
import { MIN_PASSWORD_LENGTH } from "@/modules/auth/public.client"
import type { PasswordFormValues } from "@/modules/settings/types"

const VALID_NEW = "a".repeat(MIN_PASSWORD_LENGTH)

function values(overrides: Partial<PasswordFormValues> = {}): PasswordFormValues {
  return {
    current_password: "current-password",
    new_password: VALID_NEW,
    confirm_password: VALID_NEW,
    ...overrides,
  }
}

describe("validatePasswordValues", () => {
  it("三個欄位都合法時沒有任何錯誤", () => {
    expect(Object.values(validatePasswordValues(values(), "zh")).filter(Boolean)).toEqual([])
  })

  it("舊密碼只要求非空，不套新密碼的強度規則", () => {
    // 這條守的是一個刻意的不對稱: 舊密碼可能是規則變嚴之前設的, 拿新規則擋它會讓最該
    // 換密碼的那批人反而換不了 (後端的 PasswordChange 是同一個分法)。
    const errors = validatePasswordValues(values({ current_password: "old" }), "zh")

    expect(errors.current_password).toBeUndefined()
  })

  it("舊密碼沒填要報錯", () => {
    expect(validatePasswordValues(values({ current_password: "" }), "zh").current_password)
      .toBeTruthy()
  })

  it("新密碼太短要報錯", () => {
    const short = "a".repeat(MIN_PASSWORD_LENGTH - 1)
    const errors = validatePasswordValues(
      values({ new_password: short, confirm_password: short }),
      "zh",
    )

    expect(errors.new_password).toBeTruthy()
  })

  it("新密碼與舊密碼相同要報錯", () => {
    const same = values({ current_password: VALID_NEW })

    expect(validatePasswordValues(same, "zh").new_password).toBeTruthy()
  })

  it("兩次新密碼不一致要報在確認欄位上", () => {
    const errors = validatePasswordValues(values({ confirm_password: "different" }), "zh")

    expect(errors.confirm_password).toBeTruthy()
    expect(errors.new_password).toBeUndefined()
  })

  it("新密碼自己就不合法時，不再報「兩次不一致」", () => {
    // 兩個錯誤同時亮起來的話, 使用者不知道要先改哪一個。
    const errors = validatePasswordValues(
      values({ new_password: "short", confirm_password: "" }),
      "zh",
    )

    expect(errors.new_password).toBeTruthy()
    expect(errors.confirm_password).toBeUndefined()
  })

  it("錯誤訊息跟著語系走", () => {
    const mismatched = values({ confirm_password: "different" })

    expect(validatePasswordValues(mismatched, "zh").confirm_password).not.toBe(
      validatePasswordValues(mismatched, "en").confirm_password,
    )
  })
})

describe("validateNickname", () => {
  it("有內容的暱稱通過", () => {
    expect(validateNickname("小明", "zh")).toBeUndefined()
  })

  it("空白或只有空白都視為未填", () => {
    expect(validateNickname("", "zh")).toBe("請輸入暱稱")
    expect(validateNickname("   ", "en")).toBe("Enter a nickname")
  })
})
