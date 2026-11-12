import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { SUPPORTED_LOCALES } from "@/shared/i18n/locale"
import type { RouteArea } from "@/shared/module"
import {
  AREA_ROUTES, PROTECTED_ROUTES, accessibleRoutes, isProtectedPathname, navRoutes,
} from "@/config/routes"

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")

/**
 * 各區的頁面所在的目錄 (相對 `app/`), 也就是套上該區 layout 的那一層。
 *
 * 管理區是真正的路徑段 (網址帶 `/admin`), 使用者區是 route group (不出現在網址裡)。
 */
const AREA_DIRS: Record<RouteArea, string> = {
  admin: "(protected)/admin",
  user: "(protected)/(user)",
}

/**
 * `app/` 底下每個 `page.tsx` 對應的網址路徑 → 它所在的目錄 (相對 `app/`)。
 *
 * route group (`(protected)`、`(user)`…) 只用來共用 layout, 不出現在網址裡, 所以從網址剝掉。
 */
function routesOnDisk(): Map<string, string> {
  const routes = new Map<string, string>()
  function walk(dir: string, segments: string[], dirs: string[]) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        const isGroup = /^\(.+\)$/.test(entry.name)
        walk(
          path.join(dir, entry.name),
          isGroup ? segments : [...segments, entry.name],
          [...dirs, entry.name],
        )
      } else if (entry.name === "page.tsx") {
        routes.set(`/${segments.join("/")}`.replace(/\/$/, "") || "/", dirs.join("/"))
      }
    }
  }
  walk(path.join(SRC, "app"), [], [])
  return routes
}

describe("isProtectedPathname", () => {
  it("清單裡的每一條路由都受保護", () => {
    for (const route of PROTECTED_ROUTES) {
      expect(isProtectedPathname(route.path)).toBe(true)
    }
  })

  it("子路徑也受保護", () => {
    for (const route of PROTECTED_ROUTES) {
      expect(isProtectedPathname(`${route.path}/abc123/edit`)).toBe(true)
    }
  })

  it("只是前綴相同的無關路徑不會被誤判", () => {
    // 這是 startsWith 最常見的 bug: /usersomething 並不是 /users 的子頁面。
    for (const route of PROTECTED_ROUTES) {
      expect(isProtectedPathname(`${route.path}something`)).toBe(false)
    }
  })

  it("公開路徑不受保護", () => {
    expect(isProtectedPathname("/login")).toBe(false)
    expect(isProtectedPathname("/")).toBe(false)
  })
})

describe("PROTECTED_ROUTES", () => {
  it("路徑不重複", () => {
    const paths = PROTECTED_ROUTES.map((route) => route.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it("每條路由都有以 / 開頭的路徑，且每個語系都有非空標籤", () => {
    for (const route of PROTECTED_ROUTES) {
      expect(route.path.startsWith("/")).toBe(true)
      // 逐一檢查每個語系: 只看 zh 的話, 漏翻的 en 會在導覽列上變成 undefined。
      for (const locale of SUPPORTED_LOCALES) {
        expect(route.label[locale].length).toBeGreaterThan(0)
      }
    }
  })

  // 後台管理系統本身或別人的資料: 沒宣告權限的頁面等於對所有登入的人開放。
  it("admin 區的每條路由都要宣告權限", () => {
    for (const route of AREA_ROUTES.admin) {
      expect(route.requires.length).toBeGreaterThan(0)
    }
  })

  /**
   * `ENABLED_MODULES` 加了一筆卻忘了在 `app/` 建 route adapter, 側欄會多一個連結、
   * proxy 會保護那個路徑, 但點下去是 404 —— 沒有編譯錯誤。
   */
  it("每條路由在 app/ 都有對應的 route adapter", () => {
    const onDisk = routesOnDisk()
    const missing = PROTECTED_ROUTES.map((route) => route.path).filter(
      (routePath) => !onDisk.has(routePath),
    )

    expect(missing).toEqual([])
  })

  /**
   * manifest 寫 `group: "admin"`、頁面卻放在 `(user)/` 底下時, 頁面照樣打得開, 只是套到錯的
   * 外殼, 而且繞過管理區 layout 的權限檢查 —— 沒有任何錯誤訊息。
   */
  it("每條路由的頁面放在它 group 對應的目錄底下", () => {
    const onDisk = routesOnDisk()
    const misplaced = PROTECTED_ROUTES.filter((route) => {
      const dir = onDisk.get(route.path)
      return dir === undefined || !`${dir}/`.startsWith(`${AREA_DIRS[route.group]}/`)
    }).map((route) => `${route.path} 應在 app/${AREA_DIRS[route.group]}/ 底下`)

    expect(misplaced).toEqual([])
  })

  /**
   * 反方向: 頁面建在 `(protected)/` 底下, 模組卻沒加進 `ENABLED_MODULES`。頁面照樣渲染,
   * 但沒有導覽, proxy 也不擋 (只剩 layout 的登入檢查) —— 沒有錯誤訊息。
   * 首頁由 proxy 另外處理 (`pathname === "/"`), 不在路由清單裡。
   */
  it("受保護區的每個頁面都在路由清單的保護範圍內", () => {
    const unlisted = [...routesOnDisk()]
      .filter(([routePath, dir]) => dir.startsWith("(protected)/") && routePath !== "/")
      .map(([routePath]) => routePath)
      .filter((routePath) => !isProtectedPathname(routePath))

    expect(unlisted).toEqual([])
  })

  // 管理區的 layout 掛在 `admin/` 路徑段上, 網址不在 `/admin` 底下的頁面套不到它。
  it("admin 區的每條路由網址都在 /admin 底下", () => {
    for (const route of AREA_ROUTES.admin) {
      expect(route.path.startsWith("/admin/")).toBe(true)
    }
  })

  it("user 區的路由不會落在 /admin 底下", () => {
    for (const route of AREA_ROUTES.user) {
      expect(`${route.path}/`.startsWith("/admin/")).toBe(false)
    }
  })
})

describe("navRoutes", () => {
  it("標成不出現在導覽列的路由不會列出，但仍受保護", () => {
    const hidden = PROTECTED_ROUTES.filter((route) => !route.showInNav)

    for (const route of hidden) {
      expect(navRoutes(route.group, ["*"])).not.toContain(route)
      expect(isProtectedPathname(route.path)).toBe(true)
    }
  })

  it("其餘進得去的路由都會列出", () => {
    for (const route of PROTECTED_ROUTES.filter((item) => item.showInNav)) {
      expect(navRoutes(route.group, ["*"])).toContain(route)
    }
  })
})

describe("accessibleRoutes", () => {
  // 一律從啟用清單推導, 不寫死目前有哪些路由: 新增或移除模組不該讓這批測試壞掉。
  it("只回傳該區裡有權限的路由", () => {
    for (const route of AREA_ROUTES.admin) {
      expect(accessibleRoutes("admin", route.requires)).toContain(route)
    }
    expect(accessibleRoutes("admin", ["*"]).every((route) => route.group === "admin")).toBe(true)
  })

  it("沒有任何管理權限時，管理區是空的（管理區 layout 會據此擋人）", () => {
    expect(accessibleRoutes("admin", [])).toEqual([])
  })

  it("超級管理者的萬用權限看得到整個管理區", () => {
    expect(accessibleRoutes("admin", ["*"])).toEqual(AREA_ROUTES.admin)
  })

  it("不需要權限的路由，任何登入者都看得到", () => {
    const open = PROTECTED_ROUTES.filter((route) => route.requires.length === 0)

    for (const route of open) {
      expect(accessibleRoutes(route.group, [])).toContain(route)
    }
  })
})
