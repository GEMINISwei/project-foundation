import { defineConfig, devices } from "@playwright/test"
import { ADMIN_STATE } from "./tests/support"

// 網址與超管帳密由 `make e2e check` 或 `make e2e test` (tools/commands/e2e.py)
// 起好環境之後注入。
// 沒有預設值: 漏設時打到開發中的那套 (localhost:3000) 會把測試資料寫進開發資料庫。
const baseURL = process.env.E2E_BASE_URL
if (!baseURL) {
  throw new Error("缺少 E2E_BASE_URL：請在 repo 根目錄用 make e2e test 或 make e2e check 執行")
}

export default defineConfig({
  testDir: "./tests",
  // 檔案之間平行, 同一個檔案裡的測試在同一個 worker 依序跑 (目錄依功能, 一個子功能一個檔案)。
  // 測試之間只共用準備好的帳號與登入狀態, 不共用彼此的結果 (docs/foundation/testing.md〈E2E〉)。
  // 2 個: runner 同時還要跑整套服務, 再多 CPU 會搶不過來。
  workers: 2,
  fullyParallel: false,
  // 不重試: 重試會把時序問題藏起來, 偶發失敗要修等待條件, 不是多跑一次。
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  // 本機用 dot: 全部通過時只有一行點, 失敗的細節集中在最後。AI agent 每跑一次都要把輸出整段讀進
  // 上下文, 列出每一個通過的測試只是佔位置。
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "dot",
  use: {
    baseURL,
    // 主要語系是中文, 斷言用的文案也是中文。proxy 依 Accept-Language 寫入語系 cookie。
    locale: "zh-TW",
    trace: "retain-on-failure",
  },
  projects: [
    // 超管先登入一次並保存狀態, 其他測試預設載入它; 要從未登入開始的測試自己改成 SIGNED_OUT。
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    // 裝置是每個功能都有的面向, 由 project 決定, 不開目錄。預設只跑桌機: 兩邊都跑時間加倍,
    // 同一個 IP 的登入次數也加倍 (限流)。手機上行為不同的標 @mobile (兩邊都跑),
    // 只有手機才有意義的標 @mobile-only。手機用 Chromium 模擬, CI 只裝這一個瀏覽器。
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], storageState: ADMIN_STATE },
      grepInvert: /@mobile-only/,
      dependencies: ["setup"],
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], storageState: ADMIN_STATE },
      grep: /@mobile/,
      dependencies: ["setup"],
    },
  ],
})
