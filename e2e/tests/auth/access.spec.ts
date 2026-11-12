import { expect } from "@playwright/test"
import { SIGNED_OUT, login, test } from "../support"

// 誰能進哪一區: 未登入由 proxy 導向登入頁, 沒有權限的由管理區的 layout 導回首頁。
// 兩個都從未登入開始, 不載入預設的超管登入狀態。
test.use({ storageState: SIGNED_OUT })

test("未登入進受保護頁面會導向登入頁", async ({ page }) => {
  await page.goto("/settings")

  await expect(page).toHaveURL(/\/login/)
})

test("一般帳號進入管理區會被導回首頁", async ({ page, member }) => {
  await login(page, member)

  await page.goto("/admin/users")

  await expect(page).toHaveURL("/")
})
