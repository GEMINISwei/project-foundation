/**
 * Next.js route adapter 的形狀與轉出完整性。
 *
 * `app/**​/page.tsx` 只是薄 wrapper: 從模組的 public entry 拿頁面元件、把 props 原封不動
 * 往下傳。這種接線有一個沒有任何編譯期保護的縫 —— **Next 特有的 export 不會自己跟過來**。
 * 頁面模組裡的 `export const metadata` 留在頁面模組, adapter 不寫一行就沒有; 而根 layout 的
 * `title.template` 會讓漏掉的頁面靜靜退回預設標題, 沒有錯誤訊息。`revalidate`、`dynamic`、
 * `generateStaticParams` 那些也一樣, 漏掉只會讓設定安靜地不生效。
 *
 * 所以這裡檢查兩件事:
 * 1. 頁面模組宣告的每一個 Next 特有 export, adapter 都必須轉出。
 * 2. adapter 真的是薄的 —— 只有 import、特有 export 的轉接、以及一個回傳單一 JSX 的預設輸出。
 *
 * 用 TypeScript compiler API 而不是 regex: 這支測試守的是「漏掉會安靜失敗」的東西,
 * 它自己更不能因為認不出寫法而安靜通過。認不出的 adapter 一律當作失敗。
 */

import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import ts from "typescript"
import { describe, expect, it } from "vitest"

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")

/**
 * Next 會從 page 模組讀取的所有 export。
 *
 * 這份清單是這支測試的全部價值所在 —— 每一個名字都是「漏掉不會報錯, 只會安靜失效」。
 * 升級 Next 引進新的 route segment config 時要一起加進來。
 */
const NEXT_PAGE_EXPORTS = [
  "metadata",
  "generateMetadata",
  "viewport",
  "generateViewport",
  "generateStaticParams",
  "dynamic",
  "dynamicParams",
  "revalidate",
  "fetchCache",
  "runtime",
  "preferredRegion",
  "maxDuration",
  "experimental_ppr",
]

/**
 * 就地宣告頁面、不走模組的 route 檔。
 *
 * 首頁沒有對應的模組 (它只有一段歡迎訊息), 為它開一個模組要付的維護成本高過收益。
 * 這是刻意的例外, 所以必須列在這裡 —— 清單之外的每個 route 檔都得是能被認出來的
 * 薄 adapter, 認不出來就是測試失敗。少了這條, 改寫法會讓整組檢查靜靜變成空轉。
 */
const IN_PLACE_PAGES = new Set(["app/(protected)/(user)/page.tsx"])

function filesIn(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name)
    return entry.isDirectory() ? filesIn(full) : [full]
  })
}

function parse(file: string): ts.SourceFile {
  return ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true)
}

function resolveModule(specifier: string, fromFile: string): string | null {
  const base = specifier.startsWith("@/")
    ? path.join(SRC, specifier.slice(2))
    : path.resolve(path.dirname(fromFile), specifier)

  for (const suffix of ["", ".ts", ".tsx", "/index.ts", "/index.tsx"]) {
    const candidate = `${base}${suffix}`
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate
  }
  return null
}

function hasModifier(node: ts.Node, kind: ts.SyntaxKind): boolean {
  return ts.canHaveModifiers(node)
    && (ts.getModifiers(node) ?? []).some((modifier) => modifier.kind === kind)
}

function isExported(node: ts.Node): boolean {
  return hasModifier(node, ts.SyntaxKind.ExportKeyword)
}

/** 檔案自己宣告的具名 export (不含 `export … from` 的轉出)。 */
function declaredExports(sourceFile: ts.SourceFile): Set<string> {
  const names = new Set<string>()

  for (const statement of sourceFile.statements) {
    if (!isExported(statement)) continue

    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name)) names.add(declaration.name.text)
      }
    } else if (
      (ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement))
      && statement.name
      && !hasModifier(statement, ts.SyntaxKind.DefaultKeyword)
    ) {
      names.add(statement.name.text)
    }
  }

  return names
}

/** `export { a as b } from "spec"` → 每筆轉出的「對外名字 → 來源名字」。 */
function reExports(sourceFile: ts.SourceFile) {
  return sourceFile.statements.flatMap((statement) => {
    if (
      !ts.isExportDeclaration(statement)
      || !statement.moduleSpecifier
      || !ts.isStringLiteral(statement.moduleSpecifier)
      || !statement.exportClause
      || !ts.isNamedExports(statement.exportClause)
    ) return []

    const names = new Map<string, string>()
    for (const element of statement.exportClause.elements) {
      names.set(element.name.text, (element.propertyName ?? element.name).text)
    }
    return [{ specifier: statement.moduleSpecifier.text, names }]
  })
}

/** `import { a as b } from "spec"` → 每筆引用的「本地名字 → 來源名字」。 */
function imports(sourceFile: ts.SourceFile) {
  return sourceFile.statements.flatMap((statement) => {
    if (
      !ts.isImportDeclaration(statement)
      || !ts.isStringLiteral(statement.moduleSpecifier)
      || !statement.importClause?.namedBindings
      || !ts.isNamedImports(statement.importClause.namedBindings)
    ) return []

    const names = new Map<string, string>()
    for (const element of statement.importClause.namedBindings.elements) {
      names.set(element.name.text, (element.propertyName ?? element.name).text)
    }
    return [{ specifier: statement.moduleSpecifier.text, names }]
  })
}

/** default export 的函式, 若它的 body 只是回傳單一個 JSX 元素, 回傳那個元素的標籤名。 */
function delegatedComponent(sourceFile: ts.SourceFile): string | null {
  const declaration = sourceFile.statements.find(
    (statement): statement is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(statement)
      && isExported(statement)
      && hasModifier(statement, ts.SyntaxKind.DefaultKeyword),
  )

  const body = declaration?.body
  if (!body || body.statements.length !== 1) return null

  const [only] = body.statements
  if (!ts.isReturnStatement(only) || !only.expression) return null

  const element = only.expression
  const tagName = ts.isJsxSelfClosingElement(element)
    ? element.tagName
    : ts.isJsxElement(element) ? element.openingElement.tagName : null

  return tagName && ts.isIdentifier(tagName) ? tagName.text : null
}

/** adapter 頂層只允許: import、特有 export 的轉接賦值、一個 default export function。 */
function thinnessViolations(sourceFile: ts.SourceFile): string[] {
  return sourceFile.statements.flatMap((statement) => {
    if (ts.isImportDeclaration(statement)) return []

    const isDefaultExport = hasModifier(statement, ts.SyntaxKind.DefaultKeyword)
    if (ts.isFunctionDeclaration(statement) && isDefaultExport) {
      return []
    }

    if (ts.isVariableStatement(statement) && isExported(statement)) {
      return statement.declarationList.declarations.flatMap((declaration) => {
        const name = ts.isIdentifier(declaration.name) ? declaration.name.text : "?"
        if (!NEXT_PAGE_EXPORTS.includes(name)) {
          return [`宣告了 Next 不認得的 export \`${name}\``]
        }
        if (!declaration.initializer || !ts.isIdentifier(declaration.initializer)) {
          return [`\`${name}\` 應該直接接模組轉出的值，不要在 adapter 裡就地組`]
        }
        return []
      })
    }

    return [`route 檔不該有這段（${ts.SyntaxKind[statement.kind]}）—— 邏輯屬於模組，不屬於 adapter`]
  })
}

const routeFiles = filesIn(path.join(SRC, "app"))
  .filter((file) => path.basename(file) === "page.tsx")
  .map((file) => [path.relative(SRC, file).split(path.sep).join("/"), file] as const)

describe("route adapter", () => {
  it("找得到 route 檔（避免 glob 壞掉時整組測試靜靜通過）", () => {
    expect(routeFiles.length).toBeGreaterThan(5)
  })

  it.each(routeFiles.filter(([relative]) => !IN_PLACE_PAGES.has(relative)))(
    "%s 是薄 adapter，且把頁面模組的 Next 特有 export 都轉出",
    (relative, file) => {
      const adapter = parse(file)

      expect(thinnessViolations(adapter), `${relative} 不是薄 adapter`).toEqual([])

      // 一、adapter 委派給誰。認不出來就是失敗, 不是略過。
      const componentName = delegatedComponent(adapter)
      expect(
        componentName,
        `${relative} 的預設輸出不是「回傳單一 JSX 元素」的薄 wrapper。`
        + `就地宣告頁面的 route 檔要列進 IN_PLACE_PAGES 才算數`,
      ).not.toBeNull()

      const imported = imports(adapter).find((entry) => entry.names.has(componentName!))
      expect(
        imported,
        `${relative} 的 <${componentName}> 不是從模組 public entry 引用進來的`,
      ).toBeDefined()

      // 二、順著 public entry 找到真正的頁面模組。
      const publicEntry = resolveModule(imported!.specifier, file)
      expect(publicEntry, `${relative} 的 ${imported!.specifier} 找不到對應檔案`).not.toBeNull()

      const publicSource = parse(publicEntry!)
      const exportedAs = imported!.names.get(componentName!)!
      const pageReExport = reExports(publicSource).find((entry) => entry.names.has(exportedAs))
      expect(
        pageReExport,
        `${imported!.specifier} 沒有轉出 ${exportedAs}`,
      ).toBeDefined()

      const pageFile = resolveModule(pageReExport!.specifier, publicEntry!)
      expect(pageFile, `${pageReExport!.specifier} 找不到對應檔案`).not.toBeNull()

      // 三、頁面模組宣告的每一個 Next 特有 export, adapter 都要一路帶到底。
      const pageExports = declaredExports(parse(pageFile!))
      const adapterExports = declaredExports(adapter)
      const pageRelative = path.relative(SRC, pageFile!).split(path.sep).join("/")

      for (const name of NEXT_PAGE_EXPORTS) {
        if (!pageExports.has(name)) continue
        expect(
          adapterExports.has(name),
          `${relative} 漏掉 ${name}：${pageRelative} 有定義，但沒有轉出到 route 檔。`
          + "Next 只讀 route 檔的 export，漏掉不會報錯，只會安靜失效",
        ).toBe(true)
      }

      // 反向: adapter 轉出了頁面模組根本沒有的東西, 多半是複製貼上時改漏了名字。
      for (const name of adapterExports) {
        expect(
          pageExports.has(name),
          `${relative} 轉出了 ${name}，但 ${pageRelative} 沒有定義`,
        ).toBe(true)
      }
    },
  )
})
