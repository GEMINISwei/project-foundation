// @vitest-environment node

import { readFileSync, readdirSync } from "node:fs"
import path from "node:path"
import ts from "typescript"
import { expect, it } from "vitest"

/**
 * `NEXT_PUBLIC_*` 在 build 當下就烤進 bundle, 部署後改主機的 `.env` 不會生效, 而且沒有錯誤訊息。
 * 執行期設定一律走 `shared/runtime/`。
 */

const WEB_ROOT = path.resolve(import.meta.dirname, "..")
const REPO_ROOT = path.resolve(WEB_ROOT, "../..")
const SOURCE_DIRS = ["app", "config", "modules", "shared"]
const ROOT_FILES = ["proxy.ts", "instrumentation.ts", "next.config.ts"]
const PUBLIC_ENV = /^["'`]?NEXT_PUBLIC_/

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(full)
    return /\.(ts|tsx)$/.test(entry.name) ? [full] : []
  })
}

// 用 scanner 逐個 token 看: 註解裡提到這個前綴 (解釋為什麼不用) 不算。
function publicEnvTokens(file: string): string[] {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.JSX)
  scanner.setText(readFileSync(file, "utf8"))
  const found: string[] = []
  for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
    if (PUBLIC_ENV.test(scanner.getTokenText())) found.push(scanner.getTokenText())
  }
  return found
}

it("程式碼不讀取 NEXT_PUBLIC_* 環境變數", () => {
  const files = [
    ...SOURCE_DIRS.flatMap((dir) => sourceFiles(path.join(WEB_ROOT, dir))),
    ...ROOT_FILES.map((file) => path.join(WEB_ROOT, file)),
  ]
  const offenders = files
    .filter((file) => publicEnvTokens(file).length > 0)
    .map((file) => path.relative(WEB_ROOT, file))

  expect(offenders).toEqual([])
})

it("環境設定與 compose 不定義 NEXT_PUBLIC_* 變數", () => {
  const files = [".env.example", ...readdirSync(path.join(REPO_ROOT, "infra/compose"))
    .map((name) => path.join("infra/compose", name))]
  const offenders = files.filter((file) =>
    /^\s*-?\s*NEXT_PUBLIC_\w+\s*[:=]/m.test(readFileSync(path.join(REPO_ROOT, file), "utf8")))

  expect(offenders).toEqual([])
})
