import { randomUUID } from "node:crypto"
import path from "node:path"
import { test as base, expect, type Browser, type Page } from "@playwright/test"

// 超管由 `make e2e check` 或 `make e2e test` 以 CLI 建立 (網頁上沒有建立超管的入口), 帳密每次隨機產生。
export const admin = {
  username: requireEnv("E2E_ADMIN_USERNAME"),
  password: requireEnv("E2E_ADMIN_PASSWORD"),
}

// 超管的登入狀態: auth.setup.ts 登入一次存在這裡, 之後的測試預設載入它 (playwright.config.ts)。
// 登入次數因此不隨測試數增加 —— 同一個 IP 的登入有上限, 成功也不歸零 (apps/api/modules/users/router.py)。
export const ADMIN_STATE = path.join(import.meta.dirname, "..", ".auth", "admin.json")

// 不帶任何 cookie: 驗證登入流程本身、或要用別的帳號登入的測試從這裡開始。
export const SIGNED_OUT = { cookies: [], origins: [] }

export type Account = { nickname: string; username: string; password: string }

function requireEnv(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`缺少 ${name}：請在 repo 根目錄用 make e2e test 或 make e2e check 執行`)
  return value
}

export async function login(page: Page, account: { username: string; password: string }) {
  await page.goto("/login")
  await page.getByRole("textbox", { name: "帳號" }).fill(account.username)
  await page.getByLabel("密碼", { exact: true }).fill(account.password)
  await page.getByRole("button", { name: "登入", exact: true }).click()
  await expect(page).toHaveURL("/")
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "帳號選單" }).click()
  await page.getByRole("menuitem", { name: "登出" }).click()
  await expect(page).toHaveURL(/\/login/)
}

// 用超管的登入狀態在畫面上建立一般帳號 (API 沒有對外開放)。名稱帶 uuid: 各 worker 平行建立也不會撞名,
// 同一套環境重跑也不必先清資料。
export async function createUser(
  browser: Browser,
  label: string,
  roleName?: string,
): Promise<Account> {
  const id = randomUUID().slice(0, 8)
  const account = {
    nickname: `E2E ${label} ${id}`,
    username: `e2e-${label}-${id}`,
    password: `e2e-password-${id}`,
  }
  const context = await browser.newContext({ storageState: ADMIN_STATE })
  try {
    const page = await context.newPage()
    await page.goto("/admin/users")
    await page.getByRole("button", { name: "新增使用者" }).click()
    const dialog = page.getByRole("dialog")
    await dialog.getByLabel("暱稱").fill(account.nickname)
    await dialog.getByLabel("帳號").fill(account.username)
    await dialog.getByLabel("密碼").fill(account.password)
    if (roleName) await dialog.getByLabel("角色").selectOption({ label: roleName })
    await dialog.getByRole("button", { name: "建立", exact: true }).click()
    await expect(dialog).toBeHidden()
  } finally {
    await context.close()
  }
  return account
}

// 每個 worker 一個一般帳號, 同一個 worker 的測試共用。**只能拿來當身分用**: 登出會撤銷這個帳號在所有
// 裝置上的 session (auth_version), 改密碼、改權限、停用也會影響同一個 worker 之後的測試;
// 做這些事的測試用 createUser() 建自己的帳號。
export const test = base.extend<object, { member: Account }>({
  member: [async ({ browser }, use) => use(await createUser(browser, "member")), { scope: "worker" }],
})
