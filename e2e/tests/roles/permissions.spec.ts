import { randomUUID } from "node:crypto"
import { expect, test, type Page } from "@playwright/test"
import { SIGNED_OUT, createUser, login } from "../support"

/** 超管建立一個角色並打開它的權限設定頁。 */
async function createRoleAndOpenPermissions(page: Page, name: string) {
  await page.goto("/admin/roles")
  await page.getByRole("button", { name: "新增角色" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("名稱").fill(name)
  await dialog.getByRole("button", { name: "建立", exact: true }).click()
  await expect(dialog).toBeHidden()

  await page.getByRole("row").filter({ hasText: name }).getByRole("button", { name: "操作選單" }).click()
  await page.getByRole("menuitem", { name: "管理權限" }).click()
  await expect(page.getByRole("checkbox").first()).toBeVisible()
}

// 權限選項的順序由後端決定: 使用者 (查看、新增與修改)、角色 (查看、新增與修改)。
const USERS_READ = 0
const USERS_WRITE = 1
const ROLES_READ = 2

test("只有查看權限的帳號進得了後台，但看不到新增與編輯", async ({ page, browser }) => {
  const roleName = `E2E 唯讀 ${randomUUID().slice(0, 8)}`
  await createRoleAndOpenPermissions(page, roleName)
  await page.getByRole("checkbox").nth(USERS_READ).check()
  await page.getByRole("button", { name: "儲存" }).click()
  await expect(page).toHaveURL("/admin/roles")
  await expect(page.getByRole("row").filter({ hasText: roleName })).toContainText("1 項權限")

  const viewer = await createUser(browser, "viewer", roleName)
  const context = await browser.newContext({ storageState: SIGNED_OUT })
  const viewerPage = await context.newPage()
  await login(viewerPage, viewer)

  await viewerPage.goto("/admin/users")
  await expect(viewerPage.getByRole("row").filter({ hasText: viewer.nickname })).toBeVisible()
  await expect(viewerPage.getByRole("button", { name: "新增使用者" })).toHaveCount(0)
  await expect(viewerPage.getByRole("button", { name: "操作選單" })).toHaveCount(0)

  // 沒有角色的查看權限: 導覽沒有那一項, 直接打網址也會被導回首頁。
  await expect(viewerPage.getByRole("link", { name: "角色" })).toHaveCount(0)
  await viewerPage.goto("/admin/roles")
  await expect(viewerPage).toHaveURL("/")
  await context.close()
})

test("勾選權限時自動帶上它需要的權限，取消時連動取消", async ({ page }) => {
  await createRoleAndOpenPermissions(page, `E2E 相依 ${randomUUID().slice(0, 8)}`)
  const boxes = page.getByRole("checkbox")

  await boxes.nth(USERS_WRITE).check()
  await expect(boxes.nth(USERS_READ)).toBeChecked()
  await expect(boxes.nth(ROLES_READ)).toBeChecked()

  await boxes.nth(USERS_READ).uncheck()
  await expect(boxes.nth(USERS_WRITE)).not.toBeChecked()
})
