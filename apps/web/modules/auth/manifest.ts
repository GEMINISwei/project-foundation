import type { ModuleManifest } from "@/shared/module"

// 登入是公開路由, 不進受保護路由清單。
export const AUTH_MODULE = { name: "auth", protectedRoutes: [] } as const satisfies ModuleManifest
