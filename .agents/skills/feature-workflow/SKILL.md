---
name: feature-workflow
description: 開始任何要進 main 的改動時使用（新功能、修正、文件、設定）：開分支、驗收條件、先寫測試、Draft PR、實作、等 CI、自審，到轉 Ready 交給使用者審查。
---

# 從開分支到轉 Ready 交給使用者審查

規則在 [`workflow.md`](../../../docs/foundation/workflow.md#開發流程) 與 [`testing.md`](../../../docs/foundation/testing.md)。

1. **開分支**：`gh pr list --author @me --state open` 有開著的 PR 就停下來回報；正式環境出問題才照下面的〈插隊〉。
   沒有就從最新的 `main` 開 `<type>/<kebab-case>`。一個分支只做一件事，途中發現的別的問題記下來另開。
2. **驗收條件**：每條接一個驗證方式，照 [`testing.md`](../../../docs/foundation/testing.md#驗收條件與驗證方式)
   依工作性質選；什麼時候要先給使用者確認也寫在那裡。這份驗收條件就是這個任務的範圍。
   驗收條件分屬幾件互不相依的事時，先提議拆成幾個 PR，由使用者決定；互相依賴或改到同一批檔案的才併在一起。
3. **新行為與 bug 修正先寫測試**：放該 app 的 `tests/`，與原始碼同構；改到畫面流程時 E2E 也先寫。跑單項確認紅燈
   （`uv run pytest tests/ -k xxx`、`npm run test -- -t "名稱"`、`make check integration <測試檔>`、
   `make e2e up` 後 `make e2e test <檔案>`）。重構、設定、型別整理不必先提交紅燈，直接進第 4 步。
4. **commit、push、開 Draft PR**：標題 Conventional Commits；描述照 [PR 模板](../../../.github/PULL_REQUEST_TEMPLATE.md)
   三段，驗收條件寫進「驗證」標「待實作」。commit 結尾加 `Co-authored-by`（寫到模型與版本）。
5. **實作**：測試變紅先改實作。本機依影響範圍跑需要的檢查，每個說得清楚的步驟 commit、push，照 `watch-pr` 等 CI。
   新增測試檔、在既有的測試檔加新的案例直接做，補進「驗證」段。要改既有的測試或防線檔案時照
   [`testing.md`](../../../docs/foundation/testing.md#改程式不改測試) 申請。
6. **收尾**：照 `AGENTS.md`〈改完之後〉補做（migration、`make gen-types`、相關的 E2E），push 後 CI 全綠。
7. **轉 Ready 前自己審一次**（`git diff origin/main...HEAD`）：
   - 每條驗收條件的驗證真的驗到那個條件；diff 裡對不上任何一條的，是漏寫的條件或範圍外的改動
   - 沒有順手的格式、改名、無關修正，也沒有多出條件沒要求的抽象或設定
   - 新增的註解只說明程式碼讀不出來的原因或限制；沿用別處寫法的地方，情境真的一致
   - 新增的抑制註解同一行有理由；動到防線檔案、`AGENTS.md`、skills 時，在「檢查」段說明會不會讓檢查變寬鬆
   - 讀過 `pr` 與 `ci-gate` 的 Job summary，列出的每一項都說得出原因
   - 行為或規則有變的，`AGENTS.md`、`docs/`、skills 一起改了
8. **更新 PR 描述**：「摘要」對上最新 diff，「驗證」每條寫結果（成功失敗都寫），「檢查」只列 diff 看不出、要人確認的事。
   push 後照 `watch-pr` 等 CI，全綠後 `gh pr ready <PR 號碼>` 轉 Ready for review、開始等合併，再回報使用者。
   合併由使用者做。

## 插隊

正式環境出問題、但還有 PR 開著等合併時。**要不要插隊由使用者決定**，不自己判斷「這個夠急」。

1. **說明並取得同意**：發生什麼事、影響誰、有沒有暫時處理方式；為什麼等不及開著的 PR（號碼與狀態）；
   打算怎麼修、分支名稱 `fix/<kebab-case>`。不同意就把問題記下來，回原本的 PR。
2. **修正**：從最新的 `main` 開分支，照上面第 2～8 步，驗收條件只寫這個問題，先寫能重現的測試。
   不順手整理，也不搬進行中 PR 的內容。要立刻上線照 `release`，發布前一樣要使用者同意。
3. **回到原本的 PR**：合併後切回去 `git merge origin/main`（不 rebase 審過的 commit）、push，照 `watch-pr` 等 CI，
   告訴使用者原本的 PR 已跟上。
