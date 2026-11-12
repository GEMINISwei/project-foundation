---
name: release
description: 發版：盤點相依與這一版的內容、make release 更新版號並開 PR、合併後經使用者同意才發布 release 觸發部署。只在使用者明確要求發版時使用。
disable-model-invocation: true
---

# 發版

步驟與 `make release` 的檢查見 [`operations.md`](../../../docs/foundation/operations.md)〈發版〉。

## 發布前一定要問

**發布 release 會直接部署。** 不管前面多順利、使用者之前說過什麼，發布前都停下來：給使用者看 `preview.sh` 的輸出，
問「要發布嗎？」，**等使用者在這一輪明確回答要發布**才執行 `publish.sh`。「開始發版」「好」「繼續」這類對前面步驟的同意不算。

- 只用 `.agents/skills/release/scripts/publish.sh <版號> [--prerelease]`，它會再跳一次確認。不直接下 `gh release …`，被擋就照理由做。
- pre-release 改成正式版也是發布，一樣要問。重新部署與回滾由使用者自己觸發。

## 步驟

1. **盤點**，整理給使用者並問這次的範圍：
   - 相依：落後的套件與安全更新，要不要先整批升級（[相依升級](../../../docs/foundation/workflow.md#相依升級)，另開 PR）。
   - CHANGELOG：對照 `git log --format=%s <上一個 v* tag>..origin/main` 與 `[Unreleased]`，指出漏寫的行為變更（要補走一般 PR）。
   - migration：`git diff --name-only --diff-filter=A <tag>..origin/main -- apps/api/migrations/versions`。有的話提醒發出去就不能回滾，
     同功能的可以先併（[說明](../../../docs/foundation/migrations.md#發版之前可以整理)）。
2. **版號**：依 `[Unreleased]` 提議（`1.0.0` 前不相容升 minor、其餘 patch；之後照 SemVer），確認版號與要不要先當 pre-release。
3. **`make release <版號>`**：在最新的 `main` 跑，只改 `APP_VERSION` 與 CHANGELOG 並切到 `chore/release-v<版號>`。檢查沒過就停下來回報。
4. **開 PR**：標題 `chore(release): v<版號>`，描述三段，照 `watch-pr` 等 CI 與合併。
5. **預覽**：合併後 `.agents/skills/release/scripts/preview.sh <版號> [--prerelease]`，不改任何東西；沒過就回報原因。
6. **問使用者要不要發布**（見上一節），同意才用相同參數執行 `publish.sh`。
7. **部署後**在背景等 Deploy workflow，回報每一套的結果。用了 pre-release 的，提醒觀察後可改正式版（從第 5 步不帶 `--prerelease` 重來，一樣先問）。
