import type { ModuleManifest, ProtectedRoute } from "@/shared/module"

const SETTINGS_ROUTE = {
  path: "/settings", label: { zh: "設定", en: "Settings" }, group: "user", section: null, requires: [], navIcon: "settings", showInNav: false,
} as const satisfies ProtectedRoute

export const SETTINGS_MODULE = {
  name: "settings",
  protectedRoutes: [SETTINGS_ROUTE],
} as const satisfies ModuleManifest
