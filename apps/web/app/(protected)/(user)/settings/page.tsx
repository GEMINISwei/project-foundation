import { SettingsPage, generateSettingsMetadata } from "@/modules/settings/public.server"

export const generateMetadata = generateSettingsMetadata

export default function Page() {
  return <SettingsPage />
}
