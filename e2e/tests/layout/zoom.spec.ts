import { expect, test } from "@playwright/test"

// WebApp 在手機上要像原生 App: 畫面不能縮放 (理由與代價見 docs/foundation/decisions.md 第 14 條)。
// viewport 鎖住雙指縮放, `touch-action` 擋雙擊放大; iOS Safari 分頁會忽略 `user-scalable`,
// 所以輸入框字級另外保持至少 16px, 點擊時才不會自動放大。
// 手機的 viewport 與觸控由 playwright.config.ts 的 mobile project 提供, 這裡只標 @mobile-only。
const MOBILE_ONLY = { tag: "@mobile-only" }

test("viewport 鎖住縮放，雙指不能放大畫面", MOBILE_ONLY, async ({ page }) => {
  await page.goto("/settings")

  const content = await page.locator("meta[name=viewport]").getAttribute("content")
  const directives = (content ?? "").split(",").map((part) => part.trim().replace(/\s+/g, ""))

  expect(directives).toContain("maximum-scale=1")
  expect(directives).toContain("user-scalable=no")
})

test("雙擊不會放大畫面", MOBILE_ONLY, async ({ page }) => {
  await page.goto("/settings")

  const touchAction = await page.evaluate(() => getComputedStyle(document.documentElement).touchAction)

  expect(touchAction).toBe("manipulation")
})

test("輸入框字級至少 16px，點擊時不會放大畫面", MOBILE_ONLY, async ({ page }) => {
  await page.goto("/settings")

  const inputs = page.locator("input:not([type=hidden]), select")
  await expect(inputs.first()).toBeVisible()
  const sizes = await inputs.evaluateAll((elements) =>
    elements.map((element) => Number.parseFloat(getComputedStyle(element).fontSize)),
  )

  expect(sizes.length).toBeGreaterThan(0)
  for (const size of sizes) expect(size).toBeGreaterThanOrEqual(16)
})
