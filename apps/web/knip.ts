import type { KnipConfig } from "knip"

/**
 * 未使用的檔案、匯出與相依套件的靜態檢查。用 `.ts` 而不是 `knip.json`: 例外要寫得出理由。
 *
 * **entry 只放框架的進入點與測試**, 不放 `shared/ui/index.ts`、模組的 public entry 這類公開面:
 * 進入點裡的匯出 knip 一律當作有人用, 放進來的話, 沒人用的元件與型別就會在那裡安靜地累積。
 */
const config: KnipConfig = {
  entry: [
    // Next.js 的路由慣例檔。proxy.ts 由 knip 的 Next 外掛自動認出, 不必列。
    "app/**/{page,layout,loading,error,not-found,global-error,manifest}.{ts,tsx}",
    // 測試是進入點: 它們沒有人 import, 但正是它們在使用被測的東西。
    "tests/**/*.{ts,tsx}",
  ],
  project: ["**/*.{ts,tsx}"],
  // `make gen-types` 直接跑 npx, 刻意不寫進 package.json 的 scripts
  //(理由見 package.json 的 `//scripts`), 所以靜態分析看不到它被使用。
  ignoreDependencies: ["openapi-typescript"],
  // 型別只在自己檔案裡用到仍可以 export: 那是「給這個模組的回傳值一個名字」,
  // 不是死碼。值就不一樣了 —— 只在自己檔案裡用到的函式或常數不該對外。
  ignoreExportsUsedInFile: { type: true, interface: true },
  // 目前沒有任何豁免。真的需要時, 在那個 export 的 JSDoc 標 `@knipignore` 並寫下理由 ——
  // 用 tag 而不是 `ignore: [檔案]`: 整檔忽略的範圍比理由大太多, 同一個檔案裡其他 export
  // 會一起被豁免, 哪天失去最後一個呼叫端 knip 不會出聲。
  // 「之後可能會用到」不算理由 (docs/foundation/development.md〈程式碼風格〉的「不留死碼」)。
  tags: ["-knipignore"],
}

export default config
