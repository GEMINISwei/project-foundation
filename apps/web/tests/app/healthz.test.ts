import { describe, expect, it } from "vitest"
import { GET, dynamic } from "@/app/healthz/route"

// Docker healthcheck 每 10 秒打這一支 (infra/docker/docker-compose.yml 的 web service)。
// 它一旦開始依賴後端或 session, 探活就又變回「順便測 api 活著沒」, 那正是這支端點要避開的。
describe("healthz", () => {
  it("回 200，且不依賴任何請求內容", async () => {
    const response = await GET()

    expect(response.status).toBe(200)
    await expect(response.text()).resolves.toBe("ok")
  })

  it("宣告 force-dynamic，避免 build 期被算成靜態回應", () => {
    // 靜態化之後探到的是快取, 不是還活著的伺服器 —— 伺服器掛了也會一直是 healthy。
    expect(dynamic).toBe("force-dynamic")
  })
})
