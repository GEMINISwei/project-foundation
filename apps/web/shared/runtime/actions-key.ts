/**
 * Server Action 的加解密金鑰必須由執行期提供。
 *
 * image 裡的那一把是**公開常數** (見 `apps/web/Dockerfile`), 而 Next 在環境變數缺席時會
 * 退回用它 —— 忘了注入的下場是用全世界都知道的金鑰加密閉包參數, 而且沒有任何錯誤。
 * 執行期沒給值也不放行: 這是安全性, 失敗要往「關」的方向倒。
 */
export function requireActionsEncryptionKey() {
  if (process.env.NEXT_SERVER_ACTIONS_ENCRYPTION_KEY) return

  console.error(
    "缺少 NEXT_SERVER_ACTIONS_ENCRYPTION_KEY。image 裡只有公開的 id salt，"
    + " 沒有這個環境變數的話 Server Action 會用那把公開值加密閉包參數。"
    + " 用 compose 起的話它由 web 服務的 environment 注入（值在主機的 .env，make init 會產生）。"
  )
  // `process.exit` 而不是 `throw`: Next 會接住 hook 拋出的錯誤並繼續監聽、對每個請求回 500。
  // 結束行程的話是明顯的重啟迴圈, nginx 等不到 web healthy, 不會有半套的服務上線。
  process.exit(1)
}
