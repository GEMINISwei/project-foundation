import type { MetadataRoute } from "next";

import { getPublicConfig } from "@/shared/runtime/config.server";

// manifest 預設會被靜態預算 (`next build` 的輸出裡是 `○`), 而它的 `name` 來自
// 執行期的環境變數 —— 預算掉的話同一份 image 的 PWA 名稱會永遠是建置當下的值,
// 正是 shared/runtime/config.ts 要消滅的那種靜默不一致。
// 頁面都是動態的 (讀 session cookie), 只有這一支需要明講。
export const dynamic = "force-dynamic";

export default function manifest(): MetadataRoute.Manifest {
  const appName = getPublicConfig().systemName;

  return {
    name: appName,
    short_name: appName,
    // 首頁, 不是 /users —— 後者只有超級管理者看得到, 一般使用者安裝 PWA 後
    // 會直接落在一個馬上把他導走的頁面。
    start_url: "/",
    display: "standalone",
    // 必須等於 `--color-bg-app` (`app/theme.css` 有覆寫就看那裡, 否則看 `shared/ui/styles/tokens.css`)。
    // manifest 是 JSON, 吃不到 `var()` —— 這是整個原始碼裡唯一一個 token 系統
    // 管不到的顏色, 換主題時漏改只有裝了 PWA 的人在啟動畫面看得到。
    theme_color: "#0F1115",
    icons: [
      { src: "/app-icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/app-icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/app-icon-1024.png", sizes: "1024x1024", type: "image/png" },
    ],
  };
}
