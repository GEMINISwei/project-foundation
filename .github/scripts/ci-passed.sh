#!/usr/bin/env bash
#
# 要部署的 commit 在 main 上是否已經跑過 CI 而且成功 (deploy.yml 的 ci-result job):
#
#   gh api ".../actions/workflows/ci.yml/runs?head_sha=<sha>&status=success" | ci-passed.sh <sha>
#
# 印出 true 或 false。只認 main 上 push 觸發的 run: PR 的 run 測的是 PR 的 head, 不是 squash 之後
# main 上的那個 commit (ci.yml 也不能手動執行)。API 已經依 head_sha 與 status 篩過,
# 這裡再比一次, 查詢參數寫錯時才不會把別的 commit 當成通過。
# 回應讀不懂就以非 0 結束: 不能當成「沒跑過」, 也不能當成通過。
set -euo pipefail

[ "$#" -eq 1 ] || { echo "用法：ci-passed.sh <commit sha>" >&2; exit 2; }

jq -e --arg sha "$1" '
    [.workflow_runs[]
        | select(.head_sha == $sha and .head_branch == "main" and .conclusion == "success")
        | select(.event == "push")]
    | length > 0' || [ "$?" -eq 1 ]
