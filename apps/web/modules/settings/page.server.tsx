import "server-only"
import { getCurrentUser } from "@/modules/auth/public.server"
import { api, call } from "@/shared/api/client.server"
import { getT } from "@/shared/i18n/locale.server"
import { settingsMessages } from "./i18n"
import SettingsView from "./ui/SettingsView"

export async function generateMetadata() {
  return { title: (await getT(settingsMessages))("pageTitle") }
}

export default async function SettingsPage() {
  const [user, info, t] = await Promise.all([
    getCurrentUser(),
    call(api.GET("/api/system/info")),
    getT(settingsMessages),
  ])
  const version = info.ok ? info.data.version : t("versionUnavailable")

  return <SettingsView nickname={user?.nickname ?? ""} version={version} />
}
