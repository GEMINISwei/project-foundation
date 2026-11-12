/**
 * 專案的覆寫 (`app/theme.css`) 一定要排在預設值 (`shared/ui/styles/tokens.css`) 之後。
 *
 * 兩支都是 `:root`, 誰在後面誰贏。分別在 layout 裡 import 時 bundler 不保證順序 ——
 * 實際發生過: dev 把兩支併成一支, theme.css 卻排在前面, 覆寫完全沒有作用, 畫面也沒有任何錯誤。
 * 所以 tokens.css 只能由 theme.css 的第一行 `@import` 帶進來。
 */

import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../app")

function withoutComments(source: string) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")
}

describe("theme.css 與 tokens.css 的載入順序", () => {
  it("theme.css 的第一個敘述就是載入 tokens.css", () => {
    const theme = withoutComments(fs.readFileSync(path.join(APP, "theme.css"), "utf8")).trim()

    expect(theme.startsWith('@import "../shared/ui/styles/tokens.css";')).toBe(true)
  })

  it.each(["layout.tsx", "global-error.tsx"])("%s 只載入 theme.css，不另外載入 tokens.css", (file) => {
    const source = withoutComments(fs.readFileSync(path.join(APP, file), "utf8"))

    expect(source).toContain('import "./theme.css"')
    expect(source).not.toMatch(/import\s+["'][^"']*tokens\.css["']/)
  })
})
