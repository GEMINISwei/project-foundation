"use client"

/**
 * client component 這一側的公開設定入口。形狀刻意與 `shared/i18n/context.tsx` 一致。
 *
 * 值由 root layout (Server Component) 讀好之後往下傳, 所以 client 這側永遠不碰
 * `process.env` —— 那正是這個 context 存在的理由, 見 `./config.ts`。
 */

import { createContext, use } from "react"
import { type PublicConfig, FALLBACK_PUBLIC_CONFIG } from "./config"

const PublicConfigContext = createContext<PublicConfig>(FALLBACK_PUBLIC_CONFIG)

export function PublicConfigProvider({
  config,
  children,
}: {
  config: PublicConfig
  children: React.ReactNode
}) {
  return <PublicConfigContext value={config}>{children}</PublicConfigContext>
}

/** client component 用: `const { systemName } = usePublicConfig()`。 */
export function usePublicConfig(): PublicConfig {
  return use(PublicConfigContext)
}
