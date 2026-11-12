/**
 * 依賴邊界: app/config (組裝層) → modules → shared。`npm run check:architecture` 執行,
 * `make check lint` 會跑。規則說明見 docs/foundation/architecture.md〈強制依賴規則〉。
 *
 * 不在這裡的兩條: 「模組內部用相對路徑」與「manifest 不用瀏覽器 API」是寫法層面的規則,
 * 放在 eslint.config.mjs; 「模組的檔案放置」是結構規則, 在 tests/architecture.test.ts。
 */

const PUBLIC_ENTRY = "(manifest|public\\.server|public\\.client)\\.ts$"

// UI kit 的全域樣式表 (設計變數、reset、全頁訊息)。只有文件根才載得了全域 CSS。
const GLOBAL_STYLES = "^shared/ui/styles/(tokens|base|message-page)\\.css$"

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "shared-is-bottom-layer",
      comment: "shared 不可引用 modules 或組裝層。",
      severity: "error",
      from: { path: "^shared/" },
      to: { path: "^(modules|app|config)/" },
    },
    {
      name: "module-not-to-composition",
      comment: "module 不可反向引用組裝層；需要的東西由參數或 manifest 傳進來。",
      severity: "error",
      from: { path: "^modules/" },
      to: { path: "^(app|config)/" },
    },
    {
      name: "cross-module-public-entry-only",
      comment: "跨模組只能引用對方的 public.server／public.client／manifest。",
      severity: "error",
      from: { path: "^modules/([^/]+)/" },
      to: { path: "^modules/", pathNot: ["^modules/$1/", `^modules/[^/]+/${PUBLIC_ENTRY}`] },
    },
    {
      name: "composition-public-entry-only",
      comment: "組裝層跟其他 module 一樣，只能引用 module 的 public entry 或 manifest。",
      severity: "error",
      from: { path: "^(app|config)/" },
      to: { path: "^modules/", pathNot: `^modules/[^/]+/${PUBLIC_ENTRY}` },
    },
    {
      name: "shared-ui-single-entry",
      comment:
        "UI kit 只能從 @/shared/ui 整包引用。唯一例外是文件根載入的全域樣式表"
        + "（global-error.tsx 在 root layout 之外渲染，要自己再載一次設計變數）。",
      severity: "error",
      from: { pathNot: "^shared/ui/" },
      to: {
        path: "^shared/ui/",
        pathNot: ["^shared/ui/index\\.ts$", GLOBAL_STYLES],
      },
    },
    {
      name: "shared-ui-global-css-only-from-root-layout",
      comment: "全域樣式表的例外只給文件根：app/layout.tsx 與 app/global-error.tsx。",
      severity: "error",
      from: { pathNot: ["^shared/ui/", "^app/layout\\.tsx$", "^app/global-error\\.tsx$"] },
      to: { path: GLOBAL_STYLES },
    },
    {
      name: "manifest-is-edge-safe",
      comment:
        "manifest 會被 proxy.ts 在 edge runtime 載入，**連間接依賴**都不可碰 React、Next、"
        + "server-only 或 .server 檔（例如它用到的 shared/i18n/locale.ts 也必須保持乾淨）。",
      severity: "error",
      from: { path: "^modules/[^/]+/manifest\\.ts$" },
      to: {
        path: ["^node_modules/(react|react-dom|next|server-only)/", "\\.server\\.tsx?$"],
        reachable: true,
      },
    },
  ],
  options: {
    // 要掃哪些目錄寫在 package.json 的 check:architecture (只掃產品程式碼, 測試本來就該
    // 直接指進被測目標)。不用 includeOnly: 它會把 node_modules 從圖上拿掉,
    // manifest-is-edge-safe 就永遠比對不到 react/next 而安靜失效。
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    tsPreCompilationDeps: true,
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default", "types"],
      extensions: [".ts", ".tsx", ".js", ".mjs", ".css"],
    },
  },
}
