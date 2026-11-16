import { expect } from "@playwright/test"
import { backendRequest, leakedSecrets, test } from "../support"

const site = "http://localhost:3901"

test("瀏覽器打到後端或別的網站的請求會被找出來", () => {
  expect(backendRequest(`${site}/admin/users`, site)).toBe(false)
  expect(backendRequest(`${site}/_next/static/chunk.js`, site)).toBe(false)
  expect(backendRequest("data:image/png;base64,AAAA", site)).toBe(false)
  expect(backendRequest(`${site}/api/users/me`, site)).toBe(true)
  expect(backendRequest("http://api:8000/users/me", site)).toBe(true)
})

test("Server Action 的回應裡出現 cookie 或密碼會被找出來", () => {
  const token = "eyJhbGciOiJIUzI1NiJ9.payload.signature"
  const bodies = ['0:{"ok":true}', `1:{"token":"${token}"}`]
  expect(leakedSecrets(bodies, [token, "e2e-password-ab12cd34", "short"])).toEqual([token])
})
