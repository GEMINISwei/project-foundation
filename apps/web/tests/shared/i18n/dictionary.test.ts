import { describe, expect, it } from "vitest"
import { defineMessages, translate } from "@/shared/i18n/dictionary"

const messages = defineMessages({
  zh: { hello: "你好", greet: "你好，{name}", both: "{a} 與 {b}" },
  en: { hello: "Hello", greet: "Hello, {name}", both: "{a} and {b}" },
})

describe("translate", () => {
  it("依語系取字串", () => {
    expect(translate(messages, "zh")("hello")).toBe("你好")
    expect(translate(messages, "en")("hello")).toBe("Hello")
  })

  it("替換佔位符", () => {
    expect(translate(messages, "en")("greet", { name: "Ada" })).toBe("Hello, Ada")
    expect(translate(messages, "zh")("both", { a: "甲", b: "乙" })).toBe("甲 與 乙")
  })

  it("數字會轉成字串", () => {
    expect(translate(messages, "en")("greet", { name: 42 })).toBe("Hello, 42")
  })

  it("沒給值的佔位符原樣留著", () => {
    // 替換成空字串的話, 畫面上看起來像是文案本來就少一段, 很難發現漏傳了參數。
    expect(translate(messages, "en")("greet", {})).toBe("Hello, {name}")
  })

  it("沒傳 values 時不做任何替換", () => {
    expect(translate(messages, "en")("greet")).toBe("Hello, {name}")
  })
})
