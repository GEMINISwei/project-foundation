/**
 * 寫入 session cookie 的程式, 回傳前都要經過 `withoutAccessToken` (理由見
 * `tests/shared/session/token-response.test.ts`)。
 *
 * 那支測的是函式本身; 這裡守的是「有人記得呼叫它」。新增一個簽發 token 的 action
 * (例如 refresh) 卻直接 `return res` 不會有任何症狀, 畫面照樣正常。掃的是整個專案,
 * 所以放在 `tests/` 根目錄。
 */

import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(full)
    return /\.tsx?$/.test(entry.name) ? [full] : []
  })
}

describe("寫入 session cookie 的檔案", () => {
  it("回傳前都經過 withoutData", () => {
    const writers = ["modules", "config", "shared"]
      .flatMap((dir) => sourceFiles(path.join(SRC, dir)))
      .filter((file) => !file.endsWith("access-token.server.ts"))
      .filter((file) => fs.readFileSync(file, "utf8").includes("setAccessTokenCookie("))

    expect(writers.length).toBeGreaterThan(0)
    for (const file of writers) {
      expect(fs.readFileSync(file, "utf8"), path.relative(SRC, file)).toContain("withoutData(")
    }
  })
})
