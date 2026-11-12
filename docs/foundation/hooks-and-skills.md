# AI agent 的 hooks 與 skills

同一個 repo 給 Claude 與 Codex 用，兩家可以互換、也可以互相審查對方的 PR。規則本身在 [`AGENTS.md`](../../AGENTS.md)。

```text
AGENTS.md                           兩家共用的規則 (不另設 CLAUDE.md)
.agents/skills/<name>/SKILL.md      流程 (開 PR、等 CI、發版…), 兩家共用一份
.agents/hooks/<name>.py             確認點的檢查, 兩家共用一份邏輯 (Python 標準函式庫)
.claude/settings.json               Claude 的設定: 呼叫 hook、哪些指令一定要確認
.claude/skills → ../.agents/skills  symlink
.codex/hooks.json、.codex/rules/    Codex 的設定: 同上
```

## 三層防線

1. **硬底線在 GitHub 上**：`main` 只經 PR、必過的 CI、commit 訊息檢查。agent 繞不過。
2. **hook 只擋確認點**：不可逆、碰到 `main` 或正式環境、會讓其他檢查失效的動作。只認常見的寫法。
3. **其餘由 agent 依 `AGENTS.md`〈高風險先問〉判斷**，拿不準就問。

不追求繞不過：換個寫法擋不住是已知的取捨，由 CI 與審查補。要加新的 hook 之前，先指出一次實際發生、而且現有的
檢查都沒擋下的問題。

## 目前的 hook

| 腳本 | 時機 | 做什麼 |
|---|---|---|
| `guard_commands.py` | 執行 shell 指令前 | 擋下部署、發布、合併與繞過檢查的指令；有開著的 PR 時開新分支要確認 |
| `guard_tests.py` | 用改檔工具改檔前 | 測試鎖、防線檔案 |
| `session_context.py` | 開新 session、恢復或壓縮上下文後 | 不擋，把分支、開著的 PR、測試鎖的狀態加進上下文 |

兩家的設定（事件、對象、腳本）要一致，只有最後的參數不同（`claude`／`codex`）。

### 測試鎖

實作開始之後改測試檔要使用者同意（[`testing.md`](testing.md#改程式不改測試)）。兩家的流程相同：

1. agent 用改檔工具改測試檔時被擋下。
2. agent 在對話訊息裡**一次列出**所有要改的測試檔，每個寫原因與怎麼改（簡短即可），最後才問一句是否全部同意。
   清單不放進詢問視窗：項目一多會顯示不完，使用者看不到就無法判斷。
3. 使用者同意後，agent 執行一次：

   ```bash
   python3 .agents/hooks/approve.py test apps/api/tests/modules/users/test_users.py e2e/tests/support.ts
   ```

   這個指令兩家都設成一定跳確認，使用者只按這一次。
4. 之後在**這個分支上**改這幾個檔案不再詢問；沒列到的檔案、換了分支都要重新申請。

放行記在 `.git/agent-approvals`（不進版控）。直接寫那個檔案、換個寫法執行 `approve.py` 會被擋下。
只攔改檔工具；用 shell 指令改測試檔不會被攔，由審查時看 diff 補。

### 防線檔案

決定其他檢查擋不擋得住的檔案，不分實作前後，改之前都要同意。流程與測試鎖相同，指令換成
`approve.py protected <檔案…>`：

| 類別 | 路徑 |
|---|---|
| agent 的 hook 與設定 | `.agents/hooks/`、`.claude/`、`.codex/` |
| git hook | `.githooks/` |
| CI | `.github/workflows/`、`.github/scripts/`、`.github/actions/` |
| 檢查的設定 | `apps/api/pyproject.toml`、`apps/web/package.json`、`eslint.config.mjs`、`.dependency-cruiser.cjs`、`knip.ts`、`tsconfig.json`、`vitest.config.ts`、`tools/ruff.toml` |
| 檢查的入口 | `Makefile`、`tools/commands/check.py`、`tools/commands/e2e.py` |

改了這些不會有任何檢查變紅（刪掉一個 CI 步驟照樣綠燈），所以要讓使用者看到。清單在 `protected_files.py`。
`AGENTS.md`、`docs/`、skills 刻意不保護：改了一樣在 diff 裡看得到。

### 部署與發布

發布 release 會直接部署。兩家用同一個方式：

- **唯一的出口是固定寫法的指令** `.agents/skills/release/scripts/publish.sh <版號> [--prerelease]`，
  兩家都設成一定跳確認（Claude 的 `permissions.ask`、Codex 的 `.codex/rules/publish-release.rules`）。
- **其他會部署或合併的寫法一律擋下**：push 到 `main`、`gh release create/edit/delete`、
  `gh workflow run deploy…`、`gh pr merge`、`gh pr ready`、`--no-verify`、改 `core.hooksPath`。
- `gh api` 用 GET 以外的方法、`gh run rerun` 要確認（Codex 上請使用者自己執行）。

GitHub 端刻意不設 environment 的 Required reviewers，這裡是部署前唯一的確認
（理由與什麼時候要改回來見 [`decisions.md`](decisions.md)）。

### 一次一個 PR

還有自己開著的 PR 時，開新分支、`git worktree add`、`gh pr create` 要確認。要插隊時照 `hotfix` skill 說明後，
用 `approve.py branch <分支名稱>` 申請。查不到 PR（沒網路、沒登入）時放行；Dependabot 的 PR 不算。

## Skills

| Skill | 什麼時候用 |
|---|---|
| `feature-workflow` | 任何要進 `main` 的改動：開分支、驗收條件、先寫測試、Draft PR、實作、交給使用者審查 |
| `watch-pr` | 開好或更新 PR 之後：等 CI、失敗就修、合併後同步本機 |
| `add-migration` | 改了 model 之後 |
| `hotfix` | 正式環境出問題、但還有 PR 開著 |
| `release` | 發版。只能由使用者手動呼叫 |
| `sync-foundation` | 子專案要把 foundation 的更新帶進來。只能由使用者手動呼叫 |

寫 skill 的規則：只寫步驟，細節連回 `docs/`；不寫某一家專屬的工具名稱；固定的步驟寫成 `scripts/` 裡的腳本；
會影響 repo 以外的（發版）兩家都要關掉自動觸發（`SKILL.md` 的 `disable-model-invocation: true` 與
`agents/openai.yaml` 的 `allow_implicit_invocation: false`）。這些由 `.agents/hooks/tests/test_skills.py` 檢查。

## 啟用

少了任何一項都**不會報錯**，只是那一層安靜地不生效：

- [ ] `make init dev`：把 `core.hooksPath` 設成 `.githooks`，commit 訊息才會檢查。
- [ ] PATH 上有 `python3` 3.9 以上：沒有的話 hook 只顯示錯誤、照常執行。
- [ ] **Claude**：信任這個專案，`.claude/settings.json` 與 `.claude/skills` 才會載入。
- [ ] **Codex**：信任專案的 `.codex/`（`config.toml`、`hooks.json`、`rules/`），用 `/hooks` 確認；hook 改了要重新確認。
- [ ] Windows：先 `git config --global core.symlinks true` 再 clone，`.claude/skills` 才是 symlink。

裝好後請 agent 執行 `gh pr merge 0`，確認被 hook 擋下。

## 新增一個 hook

1. 先在 `.agents/hooks/tests/` 寫測試：用 subprocess 餵 JSON 進腳本，兩家各跑一次。
2. 腳本要能在 Python 3.9 上跑。放行時什麼都不印；要擋就印 `permissionDecision` 與 agent 看了知道下一步的理由。
3. 兩份設定各加一段，事件、對象與腳本相同。

hook 的測試併在 `make check api-test` 裡執行。
