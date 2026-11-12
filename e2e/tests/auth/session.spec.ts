import { expect, test } from "@playwright/test"
import { SIGNED_OUT, createUser, login, logout } from "../support"

test("登出後其他已登入的裝置也會被登出", async ({ browser }) => {
  // 登出會撤銷這個帳號所有裝置的 session, 用 worker 共用的 member 會連累同一個 worker 之後的測試。
  const account = await createUser(browser, "logout")
  // 兩個 context 不共用 cookie, 等於兩台裝置。
  const deviceA = await browser.newContext({ storageState: SIGNED_OUT })
  const deviceB = await browser.newContext({ storageState: SIGNED_OUT })
  const pageA = await deviceA.newPage()
  const pageB = await deviceB.newPage()
  await login(pageA, account)
  await login(pageB, account)

  await logout(pageA)

  // B 的 cookie 還在, 擋下它的是後端的 auth_version 比對。
  await pageB.goto("/settings")
  await expect(pageB).toHaveURL(/\/login/)

  await deviceA.close()
  await deviceB.close()
})
