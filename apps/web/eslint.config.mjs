import { readdirSync } from "node:fs";
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// 依賴方向由 dependency-cruiser 檢查 (.dependency-cruiser.cjs); 這裡只放它看不到的「寫法」規則。
const MODULES = readdirSync(new URL("./modules", import.meta.url), { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name);

// 模組內部一律相對路徑: 同一個模組時而 `./x` 時而 `@/modules/me/x`, 要讀到路徑尾才知道
// 是自己的還是別人的; 搬動模組時也只有相對路徑會整包跟著走。
const moduleRelativeImports = MODULES.map((name) => ({
  files: [`modules/${name}/**`],
  rules: {
    "no-restricted-imports": ["error", {
      patterns: [{
        group: [`@/modules/${name}`, `@/modules/${name}/*`],
        message: "模組內部請用相對路徑（./、../）。",
      }],
    }],
  },
}));

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // 產出物, 不是我們寫的程式碼
    "coverage/**",
    "shared/api/schema.d.ts",
  ]),
  {
    // 風格規則, 數字的理由見 docs/foundation/development.md〈程式碼風格〉。
    //
    // **ESLint 卡在 9.x**: eslint-config-next 帶進來的 eslint-plugin-react peer 只到 ^9.7,
    // 裝 10 會在載入規則時就炸。移除條件: `npm view eslint-plugin-react peerDependencies`
    // 涵蓋 10。那時順便把下面 deprecated 的 max-len 換成 @stylistic。
    rules: {
      // 這裡算字元數, 後端 ruff 算顯示寬度。豁免字串: i18n 譯文本來就長。
      "max-len": ["error", {
        code: 100,
        ignoreStrings: true,
        ignoreTemplateLiterals: true,
        ignoreUrls: true,
        ignoreRegExpLiterals: true,
      }],
      // 防退步的地板, 不是重構目標。
      "max-depth": ["error", 4],
      complexity: ["error", 10],
      "max-lines-per-function": ["error", { max: 60, skipBlankLines: true, skipComments: true }],
    },
  },
  {
    // JSX 放寬: 條件渲染的每個 `&&` 都算進 complexity, JSX 的行數也不是邏輯。
    // 真正的分支邏輯要抽進 capabilities.ts 並寫測試。
    files: ["**/*.tsx"],
    rules: {
      complexity: ["error", 15],
      "max-lines-per-function": ["error", { max: 100, skipBlankLines: true, skipComments: true }],
    },
  },
  ...moduleRelativeImports,
  {
    // manifest 會被 proxy.ts 在 edge runtime 載入: 不可標成 client、不可碰瀏覽器 API。
    files: ["modules/*/manifest.ts"],
    rules: {
      "no-restricted-globals": ["error", "window", "document", "navigator", "localStorage", "sessionStorage"],
      "no-restricted-syntax": ["error", {
        selector: "ExpressionStatement[directive='use client']",
        message: "manifest 必須保持 edge-safe，不可標成 client module。",
      }],
    },
  },
  {
    // `describe` 的回呼是分組不是邏輯。complexity 仍然套用: 測試裡有分支才該警覺。
    files: ["tests/**"],
    rules: {
      "max-lines-per-function": "off",
    },
  },
]);

export default eslintConfig;
