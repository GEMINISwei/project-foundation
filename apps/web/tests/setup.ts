import "@testing-library/jest-dom"
import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers"

// jest-dom 自帶的 vitest 型別擴充的是單一參數的 `Assertion<T>`, vitest 5 的 `Assertion<R, T>`
// 有兩個參數, 宣告合併不起來 (skipLibCheck 讓它安靜失效), 斷言在執行期能跑、typecheck 卻說
// `toBeInTheDocument` 不存在。改擴充 vitest 給自訂 matcher 用的 `Matchers<R, T>`。
// 移除條件: jest-dom 的 types/vitest.d.ts 改成兩個參數 (或改擴充 Matchers) 之後。
declare module "vitest" {
  // 宣告合併只能用 interface, 空的 body 就是重點。
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Matchers<R extends void | Promise<void> = void | Promise<void>, T = unknown>
    extends TestingLibraryMatchers<T, R> {}
}
