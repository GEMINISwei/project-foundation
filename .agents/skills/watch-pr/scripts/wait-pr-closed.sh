#!/usr/bin/env bash
#
# 等 PR 離開 OPEN 狀態, 印出最後的狀態 (MERGED 或 CLOSED): wait-pr-closed.sh <PR 號碼> [間隔秒數]
#
# gh 沒有「等到合併」的指令, 只好輪詢。輪詢包在這裡, agent 只要在背景跑一次、等它結束,
# 不必自己一再查詢 (每查一次都是一輪對話的 token)。
#
# 一次可能等上好幾天: 中途查詢失敗 (網路、GitHub 暫時無法連線) 就等下一輪, 連續失敗
# MAX_FAILURES 次才放棄。第一次查詢就失敗多半是號碼錯或沒登入, 重試也不會好, 立刻結束。
set -euo pipefail

pr="${1:?用法: wait-pr-closed.sh <PR 號碼> [間隔秒數]}"
interval="${2:-60}"
readonly MAX_FAILURES=10

query() {
    local state
    state="$(gh pr view "${pr}" --json state --jq .state)" || return 1
    case "${state}" in
        OPEN | MERGED | CLOSED) echo "${state}" ;;
        *)
            echo "認不得的 PR 狀態: '${state}'" >&2
            return 1
            ;;
    esac
}

state="$(query)"
failures=0
while [ "${state}" = "OPEN" ]; do
    sleep "${interval}"
    if state="$(query)"; then
        failures=0
    else
        state="OPEN"
        failures=$((failures + 1))
        echo "查詢 PR #${pr} 失敗 (連續 ${failures}/${MAX_FAILURES} 次), 下一輪再試" >&2
        if [ "${failures}" -ge "${MAX_FAILURES}" ]; then
            echo "連續 ${MAX_FAILURES} 次查詢失敗, 不再等待" >&2
            exit 1
        fi
    fi
done
echo "${state}"
