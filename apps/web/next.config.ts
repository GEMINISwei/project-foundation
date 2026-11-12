import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  devIndicators: false,
  // `make start lan` 讓手機從區網連進來。Next dev 預設擋掉非 localhost 來源的 HMR 與 /_next,
  // 頁面會停在伺服器渲染的 HTML 而不 hydrate。只在 port 對區網開放時才連得到, 所以一律允許,
  // 開關只有 port 一個。production build 不讀這個設定。
  allowedDevOrigins: [
    "192.168.*.*",
    "10.*.*.*",
    // 172.16.0.0/12 只到 172.31, 萬用字元表達不了範圍, 逐段列出。
    ...Array.from({ length: 16 }, (_, index) => `172.${16 + index}.*.*`),
    "*.local",
  ],
  // Server Action 參數可能含密碼; 開發日誌只保留請求結果, 不展開參數。
  logging: { serverFunctions: false },
  // Next 16.3 起 `next dev` 會自動在 app 根產生 AGENTS.md 與 CLAUDE.md。這個 repo 的 agent
  // 指引只有根目錄 AGENTS.md 一份本體, 多一份自動生成的會變成沒人維護的第二來源。
  agentRules: false,
  experimental: {
    // 固定值, 刻意不開放設定: Next 把它序列化進 build 產物, 執行期改不了。這是防護用的天花板,
    // 各功能的上限寫在功能裡 (docs/foundation/new-module.md)。nginx 兩份模板的
    // client_max_body_size 要相同, tests/next.config.test.ts 守。
    serverActions: {
      bodySizeLimit: "16mb",
    },
  },
  // 這裡刻意**沒有** `/api/:path*` → 後端的 rewrite。用不到: 資料存取一律走 Server Component
  // 與 Server Action (伺服器端直接打 `API_URL`), **瀏覽器不需要任何後端路徑**。
  //
  // 日後真的需要瀏覽器直連後端 (例如 WebSocket) 時, 要在 nginx 補一條**專屬**的 location,
  // 不是把這條 rewrite 加回來 —— 理由見 infra/nginx/default.conf.template 的同一段,
  // 那裡是這個決定的 owner (**兩處要一起看**: 只關掉一邊, 請求會從另一邊繞過去)。
  //
  // 留著的代價是 Next 這台對外伺服器變成通往內網 API 的**全域代理**, 任何人都能透過它打到後端
  // 每一條路由。授權仍由後端的 permission dependency 擋, 但那是最後一道防線, 不該是唯一一道。
  //
  // **要在瀏覽器端呼叫後端時, 不要把這條加回來** —— 在模組的 `actions.ts` 包一層具名的
  // Server Action (範例見 modules/roles/actions.ts)。
};

export default nextConfig;
