#!/usr/bin/env bash
#
# 等本機 HEAD 那個 commit 的 CI 與 PR 兩個 workflow 跑完: wait-ci.sh [間隔秒數]
#
# 每個 workflow 印一行 `<workflow> <結果> <run id> [失敗的 job]`。
# 結束碼: 0 全部成功; 1 有 run 沒成功 (任何 job 一失敗就結束, 不等其他 job); 2 等不到結果 (原因在 stderr)。
#
# 不用 `gh pr checks --watch`: 它只看當下已經出現的檢查, push 之後 CI 的 run 還沒建立就結束;
# GitHub 還沒收到 push 時, 看到的是上一個 commit 早就通過的結果。
set -euo pipefail

interval="${1:-30}"
readonly WORKFLOWS=(CI PR)
# push 之後 run 通常幾秒內就出現; 等這麼多輪還沒有, 多半是 workflow 沒被觸發。
readonly MAX_WAITING=10
readonly MAX_FAILURES=10

sha="$(git rev-parse HEAD)"
if [ "$(git rev-parse '@{u}' 2>/dev/null || true)" != "${sha}" ]; then
    echo "HEAD (${sha}) 還沒 push 到 upstream, 不會有 CI 的 run" >&2
    exit 2
fi

latest_run() {
    gh run list --commit "${sha}" --workflow "$1" --limit 1 \
        --json databaseId,status,conclusion \
        --jq '.[] | "\(.databaseId) \(.status) \(.conclusion)"'
}

failed_jobs() {
    gh run view "$1" --json jobs \
        --jq '[.jobs[] | select(.conclusion == "failure") | .name] | join(",")'
}

# 查一輪, 結果放進 results (每個 workflow 一行) 與 missing; 任何查詢失敗就回傳 1。
poll() {
    local workflow run id status conclusion jobs
    results=()
    missing=()
    failed=0
    finished=0
    for workflow in "${WORKFLOWS[@]}"; do
        run="$(latest_run "${workflow}")" || return 1
        if [ -z "${run}" ]; then
            missing+=("${workflow}")
            continue
        fi
        read -r id status conclusion <<<"${run}"
        if [ "${status}" = "completed" ] && [ "${conclusion}" = "success" ]; then
            results+=("${workflow} success ${id}")
            finished=$((finished + 1))
            continue
        fi
        jobs="$(failed_jobs "${id}")" || return 1
        if [ "${status}" = "completed" ]; then
            results+=("${workflow} ${conclusion} ${id}${jobs:+ ${jobs}}")
            failed=1
        elif [ -n "${jobs}" ]; then
            results+=("${workflow} failure ${id} ${jobs}")
            failed=1
        fi
    done
}

rounds=0
failures=0
while true; do
    [ "${rounds}" -eq 0 ] || sleep "${interval}"
    rounds=$((rounds + 1))
    if ! poll; then
        if [ "${rounds}" -eq 1 ]; then
            echo "第一次查詢就失敗 (登入、repo), 不再等待" >&2
            exit 2
        fi
        failures=$((failures + 1))
        echo "查詢 CI 失敗 (連續 ${failures}/${MAX_FAILURES} 次), 下一輪再試" >&2
        if [ "${failures}" -ge "${MAX_FAILURES}" ]; then
            echo "連續 ${MAX_FAILURES} 次查詢失敗, 不再等待" >&2
            exit 2
        fi
        continue
    fi
    failures=0
    if [ "${failed}" -eq 1 ]; then
        printf '%s\n' "${results[@]}" | grep -v ' success '
        exit 1
    fi
    if [ "${finished}" -eq "${#WORKFLOWS[@]}" ]; then
        printf '%s\n' "${results[@]}"
        exit 0
    fi
    if [ "${#missing[@]}" -gt 0 ] && [ "${rounds}" -ge "${MAX_WAITING}" ]; then
        echo "等了 ${rounds} 輪還沒看到 ${missing[*]} 的 run, 確認 workflow 有沒有被觸發" >&2
        exit 2
    fi
done
