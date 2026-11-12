// 不要加上 `server-only`: 這是純函式, 抽出來就是為了能被單元測試。碰到 next/headers
// 的那一步留在呼叫端 (modules/auth/actions.ts)。

/**
 * 依 `X-Forwarded-Proto` 決定 cookie 要不要帶 `Secure`。
 *
 * 判斷跟著實際連線協定走, 不是建置期的 `NODE_ENV`: HTTP 部署自動不加、前面接上 TLS
 * 就自動加回來, 不需要改 .env。這個 header 由 nginx 覆寫: 沿用主機 reverse proxy 送來的
 * http/https, 沒送時用自己看到的協定 (infra/nginx/snippets/trusted-proxy.conf)。
 *
 * **主機的 reverse proxy 必須送 `X-Forwarded-Proto`**, 否則 nginx 只看得到主機到容器的
 * `http`, HTTPS 部署就悄悄退化成非 Secure cookie。
 */
export function resolveCookieSecure(forwardedProto: string | null | undefined): boolean {
  // 多層 proxy 會把值串成 `"https, http"`; 第一段才是面對用戶端的那一層。
  return forwardedProto?.split(",")[0]?.trim().toLowerCase() === "https"
}
