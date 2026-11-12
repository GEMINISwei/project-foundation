/**
 * `resolveLocale` 的行為必須與後端 `resolve_language()` 一致。
 *
 * 這裡的案例刻意與 `apps/api/tests/shared/test_language.py` 的表格相同 ——
 * 兩邊分頭演化的話, 症狀是「UI 是中文但錯誤訊息是英文」, 而且只在特定瀏覽器設定下重現。
 */

import { describe, expect, it } from "vitest"
import { DEFAULT_LOCALE, HTML_LANG, SUPPORTED_LOCALES, isLocale, resolveLocale } from "@/shared/i18n/locale"

describe("resolveLocale", () => {
  it.each([
    ["zh-TW,zh;q=0.9,en;q=0.8", "zh"],
    ["en-US,en;q=0.9", "en"],
    ["en", "en"],
    ["ja-JP", DEFAULT_LOCALE],
    ["", DEFAULT_LOCALE],
    [null, DEFAULT_LOCALE],
    [undefined, DEFAULT_LOCALE],
  ])("%s → %s", (header, expected) => {
    expect(resolveLocale(header)).toBe(expected)
  })

  it("取第一個支援的語言，不看 q 權重", () => {
    // 後端也是這個行為 (只做前綴比對)。兩種語言的專案不值得引入完整的內容協商。
    expect(resolveLocale("ja;q=1.0,en;q=0.1,zh;q=0.9")).toBe("en")
  })

  it("大小寫與空白不影響判斷", () => {
    expect(resolveLocale("  EN-GB ")).toBe("en")
  })
})

describe("isLocale", () => {
  it("只認支援清單裡的值", () => {
    expect(isLocale("zh")).toBe(true)
    expect(isLocale("ja")).toBe(false)
    expect(isLocale(undefined)).toBe(false)
    expect(isLocale(123)).toBe(false)
  })
})

describe("HTML_LANG", () => {
  it("每個支援的語系都有對應的 BCP 47 標籤", () => {
    for (const locale of SUPPORTED_LOCALES) {
      expect(HTML_LANG[locale]).toBeTruthy()
    }
  })
})
