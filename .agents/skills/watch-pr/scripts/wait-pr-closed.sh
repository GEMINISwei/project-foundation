#!/usr/bin/env bash
#
# 等 PR 離開 OPEN 狀態, 印出最後的狀態 (MERGED 或 CLOSED): wait-pr-closed.sh <PR 號碼> [間隔秒數]
#
# gh 沒有「等到合併」的指令, 只好輪詢。輪詢包在這裡, agent 只要在背景跑一次、等它結束,
# 不必自己一再查詢 (每查一次都是一輪對話的 token)。
set -euo pipefail

pr="${1:?用法: wait-pr-closed.sh <PR 號碼> [間隔秒數]}"
interval="${2:-60}"

while true; do
    state="$(gh pr view "${pr}" --json state --jq .state)"
    if [ "${state}" != "OPEN" ]; then
        echo "${state}"
        exit 0
    fi
    sleep "${interval}"
done
