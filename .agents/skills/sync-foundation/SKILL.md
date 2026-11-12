---
name: sync-foundation
description: 在用 foundation 建立的專案裡，把 foundation 從上次同步之後的更新帶進來，整理成一個 PR。只在使用者明確要求同步時使用。
disable-model-invocation: true
---

# 把 foundation 的更新帶進來

檔案歸誰、每種情況怎麼處理見 [`workflow.md`](../../../docs/foundation/workflow.md#與-foundation-同步)。
兩個 repo 沒有共同的 git 歷史，不要用 merge 或 cherry-pick；固定的步驟都在 `scripts/sync.py`。

1. **確認可以開始**：照 `feature-workflow` 第 1 步確認沒有開著的 PR，從最新的 `main` 開 `chore/sync-foundation`。
   找不到 `.foundation.json` 時腳本會停下來：在 foundation 本身就到此為止；在子專案則問使用者 foundation 的
   repo 位址，執行 `python3 .agents/skills/sync-foundation/scripts/sync.py init <位址>` 並 commit。
2. **看這次會帶進什麼**：`python3 .agents/skills/sync-foundation/scripts/sync.py plan`（不動任何檔案），
   輸出的第一行是舊、新兩個 commit。
   - **先理解規則變了什麼**：`git diff <舊 commit> <新 commit> -- docs/foundation AGENTS.md`。
     foundation 只寫現況，不會說明怎麼升級，差異要自己讀出來。
   - **對照這個專案**：讀 `docs/project/`（尤其〈推翻的 foundation 決定〉），判斷每一項改動在這裡要照搬、
     調整，還是不適用。專案登記了不同做法的，以專案的為準。
   - 對「有衝突」與「需要判斷」的檔案，讀 foundation 那一側的改動（同一個 `git diff`，後面換成那個檔案）。

   **把規則的變化、每一項打算怎麼處理、每個衝突怎麼解列給使用者，確認之後才往下。**
3. **套用**：`python3 .agents/skills/sync-foundation/scripts/sync.py apply`。它會改檔案並更新 `.foundation.json`，不 commit。
   改到測試檔或防線檔案被擋下時，照 `AGENTS.md`〈高風險先問〉一次列出來申請。
4. **處理腳本沒辦法決定的**：
   - 有衝突標記的檔案：兩邊的意圖都保留，處理完確認沒有殘留的 `<<<<<<<`。
   - 「需要判斷」的檔案：照第 2 步談定的做法處理。
   - 腳本直接採用、但第 2 步判斷不適用或要調整的檔案：改成談定的樣子，並在 `docs/project/` 記下與
     foundation 不同的地方。
   - 兩邊都加了 migration：Alembic 會有兩個 head，照 `add-migration` 補一支合併兩邊的。
   - `app/permissions.py`、`app/registry.py`、`config/routes.ts`：確認專案自己的模組與權限都還在。
   - `AGENTS.md`：〈本專案的規則〉保持原樣。
5. **照 `feature-workflow` 收尾**：`make gen-types`、相關的檢查、開 PR（標題 `chore: sync foundation`）。
   「摘要」寫從哪個 commit 同步到哪個 commit；「檢查」列出衝突怎麼解的，以及腳本列出的
   「子專案改了歸 foundation 的檔案」，提醒使用者那些修正要不要回到 foundation。

不帶過來的：`README.md`、`CHANGELOG.md`、版號、`docs/project/`。foundation 的改動如果讓專案的行為有變，
在專案自己的 `CHANGELOG.md` 用自己的話留一筆。
