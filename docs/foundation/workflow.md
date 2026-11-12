# 開發流程與提交

## 為什麼這樣設計

- **`main` 只透過 PR 前進，一律 squash**：`main` 一個 PR 一個 commit，PR 標題就是 commit 標題。
- **先開 Draft PR 寫驗收條件**：方向錯了在寫程式前就看得到。
- **一次一個 PR**：一次審一件事，diff 才小得好讀，也不會建立在沒審過的程式上。
- **GitHub 端用 ruleset 擋**：流程不能靠自覺。
- **AI 的 commit 寫明模型與版本**：追問題時要分得出是誰做的。

## 開發流程

```text
Feature Branch → Draft PR → Incremental Commits → Code Review → Squash Merge
```

1. **Feature Branch**：從最新的 `main` 開 `<type>/<kebab-case>`（`feat/product-list`）。一個分支只做一件事。
2. **Draft PR**：第一次 push 就開 Draft PR，描述固定三段（[模板](../../.github/PULL_REQUEST_TEMPLATE.md)）：
   - **摘要**：改了什麼、為什麼。推新 commit 時回來補。
   - **驗證**：[驗收條件](testing.md#驗收條件與測試名稱)與結果，成功失敗都寫。
   - **檢查**：diff 看不出、要審查者去確認的事。
3. **Incremental Commits**：一個 commit 一個說得清楚的步驟（先測試、再實作、再整理）。
4. **Code Review**：CI 綠、「驗證」寫完、整份 diff 自己讀過才按 Ready for review。回應意見用新的 commit，不 force push。
5. **Squash Merge**：合併後刪分支。

### 一次一個 PR

前一個 PR 合併（或關閉）後才開下一個分支。等合併時可以討論下一件事，但不開分支、不動檔案。
正式環境出問題等不及時，由使用者決定要不要插隊（AI agent 照 `hotfix` skill）。
agent 這一側由 hook 確認（[說明](hooks-and-skills.md#一次一個-pr)）；Dependabot 的 PR 不算。

### GitHub 設定

- [ ] Settings → General → Pull Requests：只勾 **Allow squash merging**，預設訊息選
  **Pull request title and commit details**，勾 **Automatically delete head branches**
- [ ] Settings → Rules：替 `main` 建 ruleset
  - **Restrict deletions**、**Block force pushes**、**Require linear history**
  - **Require a pull request before merging**，合併方式只留 **Squash**
  - **Require status checks to pass**：只加入 `ci-gate` 與 `pr`，勾 **Require branches to be up to date**。
    不要加個別的 job：docs 模式下它們會被跳過
- [ ] Settings → Advanced Security：**Dependency graph**、**Dependabot alerts**、**Dependabot security updates**
  三項都開
- [ ] 部署用的 environment 與 Variables 見 [`operations.md`](operations.md#首次設定)

## 提交與 CI

- PR 標題用 [Conventional Commits](https://www.conventionalcommits.org/zh-hant/v1.0.0/)：`<type>: <祈使句>`
  （`feat: add product list page`）。標題與描述三段由 `pr.yml` 檢查。
- commit 訊息不能有 CI 略過標記（`[skip ci]` 這類）：squash 會把它帶進 `main`，`main` 就不跑 CI。
  `.githooks/commit-msg` 會擋。

CI（`.github/workflows/ci.yml`）每個檢查各自一個 job、平行跑，跑的就是 `make check <項目>`：
`lint`、`contract`、`migrations`、`types`、`api-test`、`api-integration`、`web-test`、`build`、`e2e`。
最後由 `ci-gate` 判定，ruleset 只要求它。

- **docs 模式**：PR 改的檔案全部是 Markdown 時只跑 `api-test` 與 `web-test`，其餘跳過。
- `lint` 另外用 actionlint 與 shellcheck 檢查 workflow 與 CI 腳本。
- `e2e` 先用 Actions 的快取建好映像檔，再交給 `make e2e check`；並確認 web 的映像檔裡沒有真的 Server Action 金鑰。
- 部署由 `deploy.yml` 在發布 release 時執行（[說明](operations.md#自動部署)）。

### AI 協作的共同作者

AI 參與的 commit 在訊息最後加一行，名稱寫到**模型與版本**：

```text
feat: add product list page

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>
```

email 用工具官方的值，沒有時用 `noreply@<廠商網域>`。`.githooks/commit-msg` 在 `AI_AGENT` 有值時檢查
（Claude Code 自己會設，Codex 由 `.codex/config.toml` 補上）；要 `make init dev` 設好 `core.hooksPath` 才生效。

### 相依升級

上線後**不追最新版，只在有理由時升**（`.github/dependabot.yml`）：

- 套件與 GitHub Actions：Dependabot 只開安全更新。
- Docker 映像檔：每月一次，只送 patch。
- 整批升級：發版前盤點落後多少再決定範圍。開分支、升級、讓 CI 跑完、實際建映像檔跑起來，再開 PR。

**升級前先確認整組相容**：在乾淨的環境實際安裝並跑過檢查（型別、lint、測試、建置），不要只看版本號。
遇到 peer 相容性阻擋就**停在最新的相容版**，不用 `--force`／`--legacy-peer-deps`，並在設定檔寫下為什麼停與升級條件。

## 與 foundation 同步

子專案由 foundation 建立，之後 foundation 修正了基礎建設，子專案用 `sync-foundation` skill 帶進來
（不用 git 的 upstream，理由見 [`decisions.md`](decisions.md) 第 17 條）。

### 檔案歸誰

看路徑就知道誰可以改，同步才不會每次都衝突：

| 路徑 | 歸誰 | 規則 |
|---|---|---|
| `docs/foundation/`、`.agents/`、`.claude/`、`.codex/`、`.githooks/`、`.github/`、`tools/`、`infra/`、`Makefile` | foundation | 子專案盡量不改。要修就先修 foundation 再同步；直接改了的，同步時會列出來 |
| `docs/project/`、`README.md`、`CHANGELOG.md`、`apps/api/app/version.py`、`.foundation.json` | 子專案 | 同步時不帶 |
| 其餘（`apps/`、`e2e/`、`AGENTS.md`、`.env.example` 等） | 兩邊都會改 | 同步時三方合併，合不起來的由 agent 列出來處理 |

`AGENTS.md` 裡子專案只寫最後的〈本專案的規則〉，前面的段落跟著 foundation。

### foundation 只寫現況

**這一段只規範 foundation 這個 repo 本身，不是給子專案的寫作規則。** 子專案要不要記錄演進（CHANGELOG、
決定的狀態與取代關係、升級說明）由專案自己決定，寫在 `docs/project/` 與自己的 `CHANGELOG.md`。

foundation 的文件、註解、skill 與 hook 的提示只描述**現在**的做法：不寫「原本…現在…」，不寫從哪一版改成
什麼，也不提供升級步驟。做法變了就直接改寫。

- **為什麼**：每個子專案從不同的 commit 開始、各自做過不同的調整，foundation 寫不出對每個專案都對的升級步驟；
  夾著演進過程的文件，讀的人還得自己分辨哪一句是現在的規則。
- **子專案怎麼知道變了什麼**：同步時比對 `docs/foundation/` 與 `AGENTS.md` 在兩個 commit 之間的差異，
  理解規則與做法變了什麼，再對照自己在 `docs/project/` 記下的不同之處，決定在這個專案要照搬、調整，還是不適用。
- **foundation 本身不寫 `CHANGELOG.md`**：那一份留給子專案記自己的版本。

### 同步紀錄

子專案根目錄的 `.foundation.json`（進版控）記下 foundation 的位置與上次同步到的 commit。foundation 自己
沒有這個檔案。建立子專案時執行一次：

```bash
python3 .agents/skills/sync-foundation/scripts/sync.py init <foundation 的 repo 位址>
```

### 同步

請 agent 使用 `sync-foundation` skill。它先列出這段期間 foundation 的改動與每個檔案的處理方式，確認後才套用，
整理成一個 PR：

| 情況 | 處理 |
|---|---|
| foundation 改了，子專案沒改 | 直接採用 foundation 的版本 |
| 兩邊改的地方不重疊 | 自動合併 |
| 兩邊改到同一段，或一邊刪除一邊修改 | 留下衝突標記或列出來，由 agent 說明後處理 |
| 子專案改了歸 foundation 的檔案 | 列出來：這個修正應該回到 foundation |

Git 看不出來的衝突要另外檢查：兩邊都加了 migration（會有兩個 head）、`app/permissions.py`、`config/routes.ts`。
