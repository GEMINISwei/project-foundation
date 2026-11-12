import { getT } from "@/shared/i18n/locale.server"
import { appMessages } from "@/config/i18n"
import NotFoundView from "./not-found-view"

// 提供與應用程式一致的 404 頁面。畫面本體在 not-found-view.tsx (見該檔說明)。
export async function generateMetadata() {
  return { title: (await getT(appMessages))("notFoundTitle") }
}

export default function NotFound() {
  return <NotFoundView />
}
