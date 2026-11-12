#!/usr/bin/env bash
#
# PR 標題與描述的格式: PR_TITLE=… PR_BODY=… .github/scripts/check-pr.sh (pr.yml 呼叫, 本機也能跑)
#
# 標題 squash 後就是 main 的 commit, 要是 Conventional Commits; 描述固定「摘要、驗證、檢查」三段
# (docs/foundation/workflow.md〈開發流程〉)。`gh pr create --body` 會跳過模板, 漏了不會報錯, 所以由這裡檢查。
# 模板原樣 (只有註解與空白的 `-`、`- [ ]`) 不算寫了。
set -euo pipefail

title="${PR_TITLE:-}"
# 在 GitHub 網頁上編輯過的描述是 CRLF。
body="$(printf '%s' "${PR_BODY:-}" | tr -d '\r')"
failed=0

pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._-]+\))?!?: [^[:space:]]'
if ! [[ "${title}" =~ ${pattern} ]]; then
    echo "PR 標題要是 Conventional Commits（例：feat: add product list page），目前是「${title}」" >&2
    failed=1
fi

# 一個段落裡, 去掉 HTML 註解與模板留下的空白項目之後還剩下的行。
section() {
    printf '%s\n' "${body}" | awk -v heading="## $1" '
        /<!--/ { comment = 1 }
        comment { if (/-->/) comment = 0; next }
        $0 == heading { inside = 1; next }
        /^## / { inside = 0 }
        inside && $0 !~ /^[[:space:]]*(- \[ \]|-)?[[:space:]]*$/ { print }'
}

for name in 摘要 驗證 檢查; do
    if ! printf '%s\n' "${body}" | grep -qx "## ${name}"; then
        echo "PR 描述少了「## ${name}」段落（見 .github/PULL_REQUEST_TEMPLATE.md）" >&2
        failed=1
    elif [ -z "$(section "${name}")" ]; then
        echo "PR 描述的「${name}」還是模板原樣，請填上內容" >&2
        failed=1
    fi
done

exit "${failed}"
