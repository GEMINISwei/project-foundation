/**
 * 前後端語系清單的漂移檢查 —— **這個檔案不會被執行**, 它靠 `tsc --noEmit` 檢查。
 *
 * `Locale` 由後端的 `Language` enum 經 OpenAPI 產生, 但 `SUPPORTED_LOCALES` 是一份
 * 執行期陣列 (型別在執行期不存在, 而 proxy 的比對與設定頁的下拉選單需要真的能迭代的值)。
 * 兩者對不上時的症狀都是安靜的:
 *
 * - 後端加了語系、前端沒加 → 那個語言在設定頁不存在, 也沒人會發現
 * - 前端多列了一個後端不認得的語系 → 選了之後後端一律回退預設語系, UI 與訊息語言不一致
 *
 * `satisfies readonly Language[]` 只擋得住後者, 所以這裡補上雙向的可指派性斷言。
 * 手法同 `tests/shared/api/contract.test-d.ts`。
 *
 * 驗證方式: 在後端 `shared/http/errors.py` 的 `Language` 加一個成員、跑 `make gen-types`,
 * 底下第一行就會編譯失敗。
 */

import type { Locale } from "@/shared/i18n/locale"
import { SUPPORTED_LOCALES } from "@/shared/i18n/locale"

type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

/** 後端有、前端的執行期清單漏了 → 這一行編譯失敗。 */
export const backendCoveredByFrontend: SupportedLocale = null as unknown as Locale

/** 前端列了後端不認得的語系 → 這一行編譯失敗。 */
export const frontendCoveredByBackend: Locale = null as unknown as SupportedLocale
