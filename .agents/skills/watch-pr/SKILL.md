---
name: watch-pr
description: 開好或更新 PR 之後使用：在背景等 CI，失敗就直接修正再 push；使用者合併（或關閉）PR 後把本機同步回 main 並清掉分支。
---

# 等 CI、合併後同步本機

兩件事都在背景等、完成時通知，不要反覆查狀態。

## 1. 等 CI（每次 push 後）

`gh pr checks <PR 號碼> --watch --fail-fast`：任何一個 job 失敗就結束，不必等其他 job 跑完。
失敗時 `gh run view <run id> --log-failed` 只讀失敗段落，**直接修正、commit、push**（新的 commit 會取消還在跑的舊 run），
再回到這一步等。例外：

- 要改測試檔照 `feature-workflow` 第 5 步：一次列出、說明，使用者同意後用 `approve.py` 申請一次。
- 同一個 job 連續失敗 3 次就停下來，向使用者說明三次的原因與試過的修法。

全部通過時回報每個 job 的結果。

`e2e` 失敗自己讀，不交給子代理（修的人要讀過原因，子代理也得重讀程式碼）：
`gh run download <run id> -p 'playwright-report-*' -D <暫存目錄>`（每個失敗的份一個目錄），先讀失敗測試的 `error-context.md`，看不出來才開
trace 的特定部分，再用 `make e2e test <檔案>` 只重跑那幾個。

## 2. 等合併（交給使用者審查時開始，整個 PR 一次）

背景執行 `.agents/skills/watch-pr/scripts/wait-pr-closed.sh <PR 號碼>`，PR 不再 `OPEN` 時印出 `MERGED` 或 `CLOSED`。
session 先結束的話，使用者說 PR 已合併或關閉時照下面做（一樣先確認狀態）。不用再問使用者：

1. `git switch main && git fetch --prune && git pull --ff-only`
2. `MERGED` 才 `git branch -D` 本機分支（squash 後 git 認不出已合併）；`CLOSED` 保留分支並回報。
3. 確認 `main` 與 `origin/main` 同一個 commit，回報它。
4. 改到 `uv.lock` 或 `package-lock.json` 時提醒重裝（`apps/api` 跑 `uv sync`，`apps/web`、`e2e` 跑 `npm ci`）。
5. 有 `make e2e up` 起的環境就 `make e2e down`。
