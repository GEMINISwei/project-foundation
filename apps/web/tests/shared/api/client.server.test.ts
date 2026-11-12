import { beforeEach, describe, expect, it, vi } from "vitest"

const state = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  headers: new Map<string, string>(),
  deleted: [] as string[],
  revalidated: [] as string[],
}))

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) => {
      const value = state.cookies.get(name)
      return value === undefined ? undefined : { value }
    },
    delete: (name: string) => state.deleted.push(name),
  }),
  headers: async () => ({ get: (name: string) => state.headers.get(name) ?? null }),
}))
vi.mock("next/cache", () => ({ revalidatePath: (path: string) => state.revalidated.push(path) }))
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    throw new Error(`REDIRECT:${url}`)
  },
}))

import { api, call } from "@/shared/api/client.server"

function respond(status: number, body?: unknown) {
  const fetchMock = vi.fn<(request: Request) => Promise<Response>>(async () =>
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }))
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

beforeEach(() => {
  state.cookies.clear()
  state.headers.clear()
  state.deleted.length = 0
  state.revalidated.length = 0
  vi.spyOn(console, "error").mockImplementation(() => {})
})

describe("後端用戶端", () => {
  it("每個請求帶上語系、登入憑證、追蹤 id 與用戶端 IP", async () => {
    state.cookies.set("access_token", "jwt-token")
    state.cookies.set("locale", "en")
    state.headers.set("x-request-id", "trace-1")
    state.headers.set("x-real-ip", "203.0.113.9")
    const fetchMock = respond(200, { items: [] })

    await call(api.GET("/api/roles/options"))

    const request = fetchMock.mock.calls[0][0]
    expect(request.url).toBe("http://api:8000/api/roles/options")
    expect(Object.fromEntries(request.headers)).toMatchObject({
      "accept-language": "en",
      authorization: "Bearer jwt-token",
      "x-request-id": "trace-1",
      "x-real-ip": "203.0.113.9",
    })
  })

  it("沒登入時不帶 Authorization", async () => {
    const fetchMock = respond(200, { items: [] })

    await call(api.GET("/api/roles/options"))

    expect(fetchMock.mock.calls[0][0].headers.has("authorization")).toBe(false)
  })
})

describe("call", () => {
  it("成功時回傳資料，並重新整理指定的頁面", async () => {
    respond(201, { id: "r1" })

    const result = await call(
      api.POST("/api/roles", { body: { name: "x", permissions: [] } }),
      { revalidate: "/admin/roles" },
    )

    expect(result).toEqual({ ok: true, data: { id: "r1" } })
    expect(state.revalidated).toEqual(["/admin/roles"])
  })

  it("失敗時把後端的錯誤整理成固定的形狀，欄位錯誤變成物件", async () => {
    respond(422, {
      code: "validation.invalid",
      message: "輸入的資料不正確",
      request_id: "abc123",
      fields: [{ field: "name", message: "必填" }],
    })

    const result = await call(
      api.POST("/api/roles", { body: { name: "", permissions: [] } }),
      { revalidate: "/admin/roles" },
    )

    expect(result).toEqual({
      ok: false,
      error: {
        status: 422,
        code: "validation.invalid",
        message: "輸入的資料不正確",
        requestId: "abc123",
        fields: { name: "必填" },
      },
    })
    expect(state.revalidated).toEqual([])
  })

  it("登入失效時清掉 cookie 並導向登入頁", async () => {
    respond(401, { code: "auth.token_revoked", message: "", request_id: "r", fields: [] })

    await expect(call(api.GET("/api/users/me"))).rejects.toThrow(
      "REDIRECT:/login?reason=session-expired",
    )
    expect(state.deleted).toEqual(["access_token"])
  })

  it("登入本身回 401 時不導向，把錯誤交給表單顯示", async () => {
    respond(401, { code: "users.invalid_credentials", message: "帳號或密碼錯誤", request_id: "r", fields: [] })

    const result = await call(
      api.POST("/api/users/login", { body: { username: "a", password: "b" } }),
      { auth: "none" },
    )

    expect(result).toMatchObject({ ok: false, error: { code: "users.invalid_credentials" } })
  })

  it("連不上後端時回傳錯誤而不是丟例外，並留下帶追蹤 id 的紀錄", async () => {
    state.headers.set("x-request-id", "trace-9")
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("fetch failed")
    }))

    const result = await call(api.GET("/api/roles/options"))

    expect(result).toMatchObject({
      ok: false,
      error: { status: 503, code: "network", requestId: "trace-9" },
    })
    expect(JSON.parse(vi.mocked(console.error).mock.calls[0][0])).toMatchObject({
      event: "api_unreachable",
      request_id: "trace-9",
    })
  })
})
