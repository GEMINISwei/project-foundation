---
name: feature-workflow
description: 開始任何要進 main 的改動時使用（新功能、修正、文件、設定）：開分支、驗收條件、先寫測試、Draft PR、實作、等 CI，到交給使用者審查。
---

# 從開分支到交給使用者審查

規則在 [`workflow.md`](../../../docs/foundation/workflow.md#開發流程) 與 [`testing.md`](../../../docs/foundation/testing.md)。

1. **開分支**：`gh pr list --author @me --state open` 有開著的 PR 就停下來回報；正式環境出問題才照 `hotfix`。
   沒有就從最新的 `main` 開 `<type>/<kebab-case>`。一個分支只做一件事，途中發現的別的問題記下來另開。
2. **驗收條件**：每條接一個測試名稱（前端與 E2E 用中文句子，後端 `test_<在什麼情況下會怎樣>`）。
   寫不出測試名稱的先問。**列給使用者確認才往下**，對話裡談定的方向也一樣。
   只改 Markdown 時寫成可檢查的結果（見 [`testing.md`](../../../docs/foundation/testing.md#驗收條件與測試名稱)）。
   驗收條件分屬幾件互不相依的事時，先提議拆成幾個 PR，由使用者決定；互相依賴或改到同一批檔案的才併在一起。
3. **先寫測試**（只改 Markdown 時跳過）：放該 app 的 `tests/`，與原始碼同構；改到畫面流程時 E2E 也先寫。跑單項確認紅燈
   （`uv run pytest tests/ -k xxx`、`npm run test -- -t "名稱"`、`make check integration <測試檔>`、
   `make e2e up` 後 `make e2e test <檔案>`）。完整的檢查只在 CI 跑，本機不跑。
4. **commit 測試、push、開 Draft PR**：標題 Conventional Commits；描述照 [PR 模板](../../../.github/PULL_REQUEST_TEMPLATE.md)
   三段，驗收條件寫進「驗證」標「待實作」。commit 結尾加 `Co-authored-by`（寫到模型與版本）。
5. **實作**：測試變紅先改實作。每個說得清楚的步驟 commit、push，照 `watch-pr` 等 CI。
   要改測試時**一次列出**所有要改的測試檔，說明每一個驗證的條件與沒過的原因；使用者同意後執行一次
   `python3 .agents/hooks/approve.py test <檔案…>`（會跳一次確認），之後在這個分支上改這些檔案不再詢問。
   在「驗證」段寫出測試檔路徑與原本的斷言為什麼錯。
6. **收尾**：照 `AGENTS.md`〈改完之後〉補做（migration、`make gen-types`、相關的 E2E），push 後 CI 全綠。
7. **交給使用者前自己審一次**（`git diff origin/main...HEAD`）：
   - 每條驗收條件有對應的測試，真的斷言到那個條件；diff 裡對不上任何一條的，是漏寫的條件或範圍外的改動
   - 沒有順手的格式、改名、無關修正，也沒有多出條件沒要求的抽象或設定
   - 新增的抑制註解同一行有理由；動到防線檔案、`AGENTS.md`、skills 時，在「檢查」段說明會不會讓檢查變寬鬆
   - 行為或規則有變的，`AGENTS.md`、`docs/`、skills 一起改了
8. **更新 PR 描述**：「摘要」對上最新 diff，「驗證」每條寫結果（成功失敗都寫），「檢查」只列 diff 看不出、要人確認的事。
   push 後照 `watch-pr` 等 CI 並開始等合併，再回報使用者。Ready for review 與合併由使用者做。
