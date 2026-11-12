// Server Component 與 Server Action 這一側的入口。
//
// 帶 `server-only` 而不是 `"use server"`: 這不是 Server Action, 只是伺服器端的讀取函式。
import "server-only"

import { type PublicConfig, readPublicConfig } from "./config"

/**
 * 這個行程當下的公開設定。
 *
 * `process.env` 在**函式裡**讀, 不是在模組層級算一次存成常數: 模組層級的初始化會在
 * `next build` 的預先渲染階段就被求值, 那時候的環境變數是建置環境的, 不是部署主機的
 * —— 而那正是這整個模組要消滅的失敗模式 (見 ./config.ts)。
 */
export function getPublicConfig(): PublicConfig {
  return readPublicConfig(process.env)
}
