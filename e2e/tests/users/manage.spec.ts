import { randomUUID } from "node:crypto"
import { expect, test } from "@playwright/test"
import { createUser } from "../support"

// 預設載入超管的登入狀態 (playwright.config.ts)。
test("超級管理者新增使用者後，列表看得到該使用者", async ({ page }) => {
  const id = randomUUID().slice(0, 8)
  const nickname = `E2E 新使用者 ${id}`
  await page.goto("/admin/users")

  await page.getByRole("button", { name: "新增使用者" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("暱稱").fill(nickname)
  await dialog.getByLabel("帳號").fill(`e2e-new-${id}`)
  await dialog.getByLabel("密碼").fill(`e2e-password-${id}`)
  await dialog.getByRole("button", { name: "建立", exact: true }).click()

  await expect(dialog).toBeHidden()
  // 列表在桌面寬度下沒有帳號欄, 以暱稱辨認。
  await expect(page.getByRole("cell", { name: nickname, exact: true })).toBeVisible()
})

test("新增使用者與重設密碼的密碼欄位標成新密碼", async ({ page, browser }) => {
  // 自己建一個: 列表新的在前, 剛建的一定在第一頁。
  const account = await createUser(browser, "autocomplete")
  // 沒標的話, 瀏覽器的密碼管理員會把這裡當成管理者自己的登入表單: 自動填入管理者的密碼,
  // 送出後還會提示「更新已儲存的密碼」, 把管理者存的密碼換成別人的。
  await page.goto("/admin/users")

  await page.getByRole("button", { name: "新增使用者" }).click()
  const createDialog = page.getByRole("dialog")
  await expect(createDialog.getByLabel("密碼")).toHaveAttribute("autocomplete", "new-password")
  await createDialog.getByRole("button", { name: "取消" }).click()

  const row = page.getByRole("row").filter({ hasText: account.nickname })
  await row.getByRole("button", { name: "操作選單" }).click()
  await page.getByRole("menuitem", { name: "重設密碼" }).click()
  await expect(page.getByRole("dialog").getByLabel("新密碼")).toHaveAttribute("autocomplete", "new-password")
})
