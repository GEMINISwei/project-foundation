// Docker healthcheck 的探活端點 (infra/docker/docker-compose.yml 的 web service)。
//
// 刻意不碰後端: 這裡只回答「Next.js 伺服器還在回應嗎」。**不要改成探 `/login`** ——
// 那一頁會 server-render, 日後只要它多打一支 API, 就等於每 10 秒多一次
// API + 資料庫查詢; 而且 api 一有狀況 web 就跟著被判定不健康 —— api 自己已經有 healthcheck,
// `depends_on: api: service_healthy` 也已經表達了依賴, web 再重複判一次只會讓故障範圍
// 看起來比實際大。
//
// 這支是 `app/` 底下唯一的 route handler, 允許的內容見 docs/foundation/architecture.md 的分級規則。
// 命名維持避開 `/api`: 那個前綴在這個專案裡專指「後端的東西」, 而 nginx 刻意沒有把任何
// `/api/` 路徑對外開放 (見 infra/nginx/default.conf.template)。在 Next 這邊開一條
// `/api/...` 只會讓兩邊的意思對不起來。

// build 期不要把它算成靜態回應 —— 那樣探到的是快取, 不是還活著的伺服器。
export const dynamic = "force-dynamic"

export async function GET() {
  return new Response("ok", { headers: { "cache-control": "no-store" } })
}
