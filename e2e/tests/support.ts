import { randomUUID } from "node:crypto"
import path from "node:path"
import {
  test as base,
  expect,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test"

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
  passwords.add(account.password)
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
export function backendRequest(url: string, site: string): boolean {
  if (!/^https?:/.test(url)) return false
  const target = new URL(url)
  return target.origin !== new URL(site).origin || target.pathname.startsWith("/api/")
}

export function leakedSecrets(bodies: string[], secrets: string[]): string[] {
  return [...new Set(secrets)].filter(
    (secret) => secret.length >= 12 && bodies.some((body) => body.includes(secret)),
  )
}

const passwords = new Set<string>()
const observed = new WeakSet<BrowserContext>()
const watch = {
  problems: [] as string[],
  actionBodies: [] as Promise<string>[],
  pending: [] as Promise<unknown>[],
  cookies: new Set<string>(),
}

function site(): string {
  return requireEnv("E2E_BASE_URL")
}

function observe(context: BrowserContext) {
  if (observed.has(context)) return
  observed.add(context)
  context.on("request", (request) => {
    if (backendRequest(request.url(), site())) {
      watch.problems.push(`瀏覽器直接呼叫後端：${request.method()} ${request.url()}`)
    }
  })
  context.on("response", (response) => {
    const cookies = response.headerValues("set-cookie").then((values) => {
      for (const value of values) watch.cookies.add(value.split(";")[0].split("=").slice(1).join("="))
    })
    watch.pending.push(cookies.catch(() => undefined))
    if (response.request().headers()["next-action"]) {
      watch.actionBodies.push(response.text().catch(() => ""))
    }
  })
}

async function contractProblems(context: BrowserContext): Promise<string[]> {
  await Promise.all(watch.pending)
  for (const cookie of await context.cookies()) watch.cookies.add(cookie.value)
  const bodies = await Promise.all(watch.actionBodies)
  const secrets = [...watch.cookies, admin.password, ...passwords]
  const leaks = leakedSecrets(bodies, secrets).map(
    (secret) => `Server Action 的回應帶出 cookie 或密碼：${secret.slice(0, 6)}…`,
  )
  const problems = [...watch.problems, ...leaks]
  watch.problems = []
  watch.actionBodies = []
  watch.pending = []
  return problems
}

export const test = base.extend<{ contracts: void }, { member: Account; contexts: void }>({
  contexts: [
    async ({ browser }, use) => {
      const newContext = browser.newContext.bind(browser)
      browser.newContext = async (options) => {
        const context = await newContext(options)
        observe(context)
        return context
      }
      await use()
    },
    { scope: "worker", auto: true },
  ],
  member: [async ({ browser }, use) => use(await createUser(browser, "member")), { scope: "worker" }],
  contracts: [
    async ({ context }, use) => {
      observe(context)
      await use()
      expect(await contractProblems(context), "執行期契約").toEqual([])
    },
    { auto: true },
  ],
})
