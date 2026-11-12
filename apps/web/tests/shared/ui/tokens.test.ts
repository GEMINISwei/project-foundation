/**
 * `shared/` 用到的每一個 CSS 變數都要在 `shared/` 裡有定義。
 *
 * 設計變數若只定義在專案的 `app/theme.css`, 換主題或拿掉那一行覆寫時不會有任何錯誤 ——
 * 瀏覽器把解不出來的 `var(--…)` 當成沒寫, 畫面只是安靜地失去樣式。這支測試把那個縫關掉:
 * 新增變數要加在 `shared/ui/styles/tokens.css` (給預設值), 專案只在 theme.css 覆寫。
 */

import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..")
const SHARED = path.join(SRC, "shared")

function filesUnder(dir: string, extensions: readonly string[]): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === "generated" ? [] : filesUnder(full, extensions)
    return extensions.some((extension) => entry.name.endsWith(extension)) ? [full] : []
  })
}

// 註解裡的 `var(--space-n)` 這類示意寫法不算使用。
function withoutComments(source: string) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")
}

function collect(pattern: RegExp, files: string[]) {
  const names = new Set<string>()
  for (const file of files) {
    for (const match of withoutComments(fs.readFileSync(file, "utf8")).matchAll(pattern)) {
      names.add(match[1])
    }
  }
  return names
}

describe("shared 的 CSS 變數", () => {
  const sources = filesUnder(SHARED, [".css", ".ts", ".tsx"])

  it("每一個用到的變數都定義在 shared 裡", () => {
    const used = collect(/var\(\s*--([a-z0-9-]+)\s*[,)]/g, sources)
    // 定義的來源有兩種: CSS 的 `--x: …`, 以及元件用 inline style 設的 `"--x"` (例: Flex)。
    const defined = new Set([
      ...collect(/(?:^|[\s;{])--([a-z0-9-]+)\s*:/g, sources),
      ...collect(/["'`]--([a-z0-9-]+)["'`]/g, sources),
    ])

    expect(used.size).toBeGreaterThan(0)
    expect([...used].filter((name) => !defined.has(name)).sort()).toEqual([])
  })
})
