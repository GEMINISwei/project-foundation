/**
 * `readPublicConfig` 的重點不是「回傳正確的欄位」, 是它怎麼處理缺值。
 *
 * 這整個模組存在的理由是「image 建一次、部署到哪都吃當下主機的設定」,
 * 所以它必須把「少設一個變數」跟「刻意設成空」分開: 前者要看得出來, 後者要原樣生效。
 * 搞反的話兩種情況都只會安靜地顯示錯的東西。
 *
 * 目前只有 `systemName` 一個欄位, 而它屬於前者。新增「空字串是有效設定」的欄位時
 * (例如可以留空的公開金鑰), 要在這裡補一條測它走 `??` 而不是 `||` ——
 * 那個不對稱從程式碼上看不出是刻意的。
 */

import { describe, expect, it } from "vitest"
import { FALLBACK_PUBLIC_CONFIG, readPublicConfig } from "@/shared/runtime/config"

describe("readPublicConfig", () => {
  it("讀傳進來的環境變數", () => {
    expect(readPublicConfig({ SYSTEM_NAME: "測試系統" })).toEqual({ systemName: "測試系統" })
  })

  it("systemName 沒設或為空字串都退回佔位字", () => {
    // 空字串也要走 fallback: `.env` 裡寫 `SYSTEM_NAME=` 的話側欄與分頁標題會整個消失,
    // 看起來像渲染壞掉, 而不是像少設了一個變數。
    expect(readPublicConfig({}).systemName).toBe(FALLBACK_PUBLIC_CONFIG.systemName)
    expect(readPublicConfig({ SYSTEM_NAME: "" }).systemName).toBe(FALLBACK_PUBLIC_CONFIG.systemName)
  })
})
