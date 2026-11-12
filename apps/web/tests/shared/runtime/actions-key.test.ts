// @vitest-environment node

import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { requireActionsEncryptionKey } from "@/shared/runtime/actions-key"

/**
 * 沒有金鑰時 Server Action 會改用 image 裡的公開值加密, 而且沒有任何錯誤, 所以失敗要往「關」的方向倒:
 * 結束行程, 不能只丟例外 (Next 會接住, 繼續對每個請求回 500)。
 */

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {})
  vi.spyOn(process, "exit").mockImplementation((() => undefined) as never)
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

it("沒有金鑰時印出錯誤並結束行程", () => {
  vi.stubEnv("NEXT_SERVER_ACTIONS_ENCRYPTION_KEY", "")

  requireActionsEncryptionKey()

  expect(console.error).toHaveBeenCalledWith(expect.stringContaining("NEXT_SERVER_ACTIONS_ENCRYPTION_KEY"))
  expect(process.exit).toHaveBeenCalledWith(1)
})

it("有金鑰時不結束行程", () => {
  vi.stubEnv("NEXT_SERVER_ACTIONS_ENCRYPTION_KEY", "runtime-key")

  requireActionsEncryptionKey()

  expect(process.exit).not.toHaveBeenCalled()
  expect(console.error).not.toHaveBeenCalled()
})
