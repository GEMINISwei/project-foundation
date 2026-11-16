#!/usr/bin/env bash
#
# ci.yml 的總閘 (ci-gate job): 等全部 job 跑完, 判定這次 CI 過不過。
#
#   echo '${{ toJSON(needs) }}' | ci-gate.sh <docs|full>
#
# main 的 ruleset 只要求 ci-gate, 所以跳過要分清楚: 被跳過的 required check 在 GitHub 上算通過。
# - 每個 job 都要 success; 只有 docs 模式下、不在 ALWAYS_REQUIRED 裡的 job 可以是 skipped。
# - 模式不是 docs 或 full (changes 失敗時是空的) 就失敗: 連哪些可以跳過都不知道。
# 輸入讀不懂也以非 0 結束。
# 有 GITHUB_STEP_SUMMARY 時把結果寫進 Job summary: 只列沒過的 job, 全部通過時只有一行。
set -euo pipefail

# 每種模式都要跑的 job, 也就是 ci.yml 裡沒有 job 層級 if 的那些 (測試比對兩邊一致)。
ALWAYS_REQUIRED="changes api-test web-test"

[ "$#" -eq 1 ] || { echo "用法：echo '<needs JSON>' | ci-gate.sh <docs|full>" >&2; exit 2; }
mode="$1"
case "${mode}" in
    docs | full) ;;
    *)
        echo "不知道這次是哪種模式（「${mode}」），changes job 可能失敗了" >&2
        exit 1
        ;;
esac

failed="$(jq -r --arg mode "${mode}" --arg always "${ALWAYS_REQUIRED}" '
    ($always | split(" ")) as $required
    | to_entries[]
    | select(.value.result != "success")
    | select(
        ($mode == "docs" and .value.result == "skipped" and (.key | IN($required[])) == false)
        | not)
    | "\(.key): \(.value.result)"')"

summary="${GITHUB_STEP_SUMMARY:-/dev/null}"
if [ -n "${failed}" ]; then
    echo "沒有通過的 job（${mode} 模式）：" >&2
    printf '  %s\n' "${failed}" >&2
    {
        printf '### 沒有通過的 job（%s 模式）\n\n| job | 結果 |\n|---|---|\n' "${mode}"
        printf '%s\n' "${failed}" | sed 's/^\([^:]*\): \(.*\)$/| \1 | \2 |/'
    } >> "${summary}"
    exit 1
fi
echo "全部通過（${mode} 模式）"
echo "全部通過（${mode} 模式）" >> "${summary}"
