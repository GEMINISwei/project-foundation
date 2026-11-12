// @vitest-environment node

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

/**
 * dependency-cruiser 與 ESLint 管不到的結構規則: 模組的檔案放置。
 *
 * 依賴方向由 dependency-cruiser 檢查 (.dependency-cruiser.cjs), 寫法規則在 eslint.config.mjs。
 * 規則說明見 docs/foundation/architecture.md〈Frontend module 介面〉。
 */

const MODULES_DIR = path.resolve(import.meta.dirname, "../modules")
const modules = readdirSync(MODULES_DIR, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())

function entries(dir: string) {
  return readdirSync(dir, { withFileTypes: true })
}

it("掃得到模組", () => {
  // 路徑算錯時「沒有模組」與「全部通過」看起來一樣。
  expect(modules.length).toBeGreaterThan(0)
})

describe.each(modules.map((entry) => entry.name))("modules/%s", (name) => {
  const dir = path.join(MODULES_DIR, name)
  const files = entries(dir).filter((entry) => entry.isFile()).map((entry) => entry.name)

  it("必備 manifest.ts、i18n.ts 與至少一個 public entry", () => {
    expect(files).toContain("manifest.ts")
    expect(files).toContain("i18n.ts")
    expect(files.some((file) => /^public\.(server|client)\.ts$/.test(file))).toBe(true)
  })

  it("底下只能有 ui/，ui/ 底下不再分層（不要開 components/、hooks/、utils/）", () => {
    const subdirs = entries(dir).filter((entry) => entry.isDirectory()).map((entry) => entry.name)
    expect(subdirs.filter((sub) => sub !== "ui")).toEqual([])

    if (subdirs.includes("ui")) {
      const nested = entries(path.join(dir, "ui")).filter((entry) => entry.isDirectory())
      expect(nested.map((entry) => entry.name)).toEqual([])
    }
  })
})

describe("tests/ 與原始碼同構", () => {
  const SRC = path.resolve(import.meta.dirname, "..")
  const TESTS = path.join(SRC, "tests")
  // 不對應任何原始碼目錄、但有正當理由存在的測試目錄。
  const ALLOWED = new Set(["stubs"])

  function directoriesUnder(dir: string): string[] {
    return entries(dir)
      .filter((entry) => entry.isDirectory())
      .flatMap((entry) => {
        const full = path.join(dir, entry.name)
        return [full, ...directoriesUnder(full)]
      })
  }

  it("每個測試目錄都對應到同名的原始碼目錄", () => {
    // 放錯目錄的測試照樣會跑, 只是「這個模組有沒有測試」從此找不到; 刪模組時也不會被一起刪掉。
    const strays = directoriesUnder(TESTS)
      .map((dir) => path.relative(TESTS, dir))
      .filter((relative) => !ALLOWED.has(relative.split(path.sep)[0]))
      .filter((relative) => !isDirectory(path.join(SRC, relative)))

    expect(strays).toEqual([])
  })

  function isDirectory(dir: string) {
    return existsSync(dir) && statSync(dir).isDirectory()
  }
})

describe("main 地標由外殼提供", () => {
  // `(protected)` 兩區的 `<main>` 在 `config/shell/AreaLayout.tsx`。頁面再出一個就是巢狀的
  // 主要地標: 畫面看不出來, 螢幕閱讀器會看到兩塊「主要內容」。登入、註冊這類公開頁面沒有外殼,
  // 由它們自己提供 —— 所以只檢查掛在受保護區的模組 (manifest 有 protectedRoutes 的那些)。
  const SRC = path.resolve(import.meta.dirname, "..")
  const MAIN = /<main[\s>]|as="main"/

  function sourceFiles(dir: string): string[] {
    return entries(dir).flatMap((entry) => {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) return sourceFiles(full)
      return /\.tsx?$/.test(entry.name) ? [full] : []
    })
  }

  const protectedModules = modules
    .map((entry) => entry.name)
    .filter((name) => {
      const manifest = readFileSync(path.join(MODULES_DIR, name, "manifest.ts"), "utf8")
      return !/protectedRoutes:\s*\[\s*\]/.test(manifest)
    })

  it("受保護區的頁面與模組不渲染自己的 <main>", () => {
    const files = [
      ...sourceFiles(path.join(SRC, "app", "(protected)")),
      ...protectedModules.flatMap((name) => sourceFiles(path.join(MODULES_DIR, name))),
    ]
    const offenders = files
      .filter((file) => MAIN.test(readFileSync(file, "utf8")))
      .map((file) => path.relative(SRC, file))

    expect(protectedModules.length).toBeGreaterThan(0)
    expect(offenders).toEqual([])
  })
})

/**
 * dependency-cruiser 只掃 `check:architecture` 列出的路徑。新增的原始碼目錄或根目錄的
 * 執行期檔案沒加進去的話, 那一層不受邊界規則管, 而且不會報錯。
 */
describe("依賴邊界的掃描範圍", () => {
  const WEB_ROOT = path.resolve(import.meta.dirname, "..")
  // 不是應用程式原始碼: 測試、產出物、靜態檔與工具設定。
  const NOT_SOURCE = new Set(["tests", "node_modules", "coverage", "public", "knip.ts"])
  const isToolingConfig = (name: string) => /\.config\.ts$|\.d\.ts$/.test(name)

  function hasSource(dir: string): boolean {
    return entries(dir).some((entry) => entry.isDirectory()
      ? hasSource(path.join(dir, entry.name))
      : /\.(ts|tsx)$/.test(entry.name))
  }

  it("每個原始碼目錄與根目錄的執行期檔案都在 check:architecture 裡", () => {
    const pkg = JSON.parse(readFileSync(path.join(WEB_ROOT, "package.json"), "utf8"))
    const scanned = new Set(pkg.scripts["check:architecture"].split(/\s+/))
    const sources = entries(WEB_ROOT)
      .filter((entry) => !entry.name.startsWith(".") && !NOT_SOURCE.has(entry.name))
      .filter((entry) => entry.isDirectory()
        ? hasSource(path.join(WEB_ROOT, entry.name))
        : /\.(ts|tsx)$/.test(entry.name) && !isToolingConfig(entry.name))
      .map((entry) => entry.name)

    expect(sources.filter((name) => !scanned.has(name))).toEqual([])
  })
})
