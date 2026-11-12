#!/usr/bin/env bash
#
# 確認 GHCR 上每個標籤的 image 都還完整 (deploy.yml 的 cleanup-ghcr 清掉 untagged 之後執行):
#
#   ghcr-verify.sh <image>...   例如 ghcr.io/<帳號>/<repo>-api; 需要 GITHUB_ACTOR、GITHUB_TOKEN
#                               與 GITHUB_STEP_SUMMARY
#
# 檢查 registry 上的所有標籤, 不只這次部署的組: 只部署 production 時, staging 的 image 被誤刪
# 也要在這次被發現, 不能等到 staging 下次部署才拉不到。
# 有 attestation 時標籤指向 index, 真正的 image 是它引用的子 manifest, 在 GHCR 上也顯示成
# untagged —— 清理工具誤刪的就會是它們, 所以逐一確認 index 引用的每個 manifest 都還在。
# 清理工具自己的 validate 只留 warning, 不會讓步驟失敗, 所以另外寫這支。
#
# 結果寫成表格附加到 GITHUB_STEP_SUMMARY; 缺漏寫成 ::error:: 到 stdout, 有任何缺漏就以 1 結束。
#
# 要能在 macOS 內建的 bash 3.2 跑 (它的測試也會在本機執行)。
set -euo pipefail

ACCEPT="application/vnd.oci.image.index.v1+json"
ACCEPT+=",application/vnd.docker.distribution.manifest.list.v2+json"
ACCEPT+=",application/vnd.oci.image.manifest.v1+json"
ACCEPT+=",application/vnd.docker.distribution.manifest.v2+json"

[ "$#" -gt 0 ] || { echo "用法：ghcr-verify.sh <image>..." >&2; exit 2; }
: "${GITHUB_ACTOR:?}" "${GITHUB_TOKEN:?}" "${GITHUB_STEP_SUMMARY:?}"

token=""
registry() {
    curl -fsS -H "Authorization: Bearer ${token}" -H "Accept: ${ACCEPT}" "$@"
}

failed=0
rows=""
for image in "$@"; do
    repo="${image#ghcr.io/}"
    # registry API 要的是 registry 自己發的 token, 用 GITHUB_TOKEN 換; 私有 package 也能讀。
    if ! token="$(curl -fsS -u "${GITHUB_ACTOR}:${GITHUB_TOKEN}" \
            "https://ghcr.io/token?scope=repository:${repo}:pull" | jq -r .token)" \
        || ! tags="$(registry "https://ghcr.io/v2/${repo}/tags/list" | jq -r '.tags // [] | .[]')"; then
        echo "::error::無法列出 ${image} 的標籤"
        rows+="| ${image} | — | ❌ 無法列出標籤 |"$'\n'
        failed=1
        continue
    fi
    if [ -z "${tags}" ]; then
        # 剛 push 過, 至少有這次部署的組名; 一個都沒有代表標籤也被刪了。
        echo "::error::${image} 沒有任何標籤"
        rows+="| ${image} | — | ❌ 沒有任何標籤 |"$'\n'
        failed=1
        continue
    fi
    for tag in ${tags}; do
        if ! manifest="$(registry "https://ghcr.io/v2/${repo}/manifests/${tag}")"; then
            echo "::error::${image}:${tag} 讀不到 manifest"
            rows+="| ${image} | ${tag} | ❌ 讀不到 manifest |"$'\n'
            failed=1
            continue
        fi
        missing=""
        count=0
        for digest in $(jq -r '.manifests // [] | .[].digest' <<< "${manifest}"); do
            count=$((count + 1))
            registry -I "https://ghcr.io/v2/${repo}/manifests/${digest}" > /dev/null \
                || missing+=" ${digest}"
        done
        if [ -n "${missing}" ]; then
            echo "::error::${image}:${tag} 引用的 manifest 不見了：${missing# }"
            rows+="| ${image} | ${tag} | ❌ 缺少${missing} |"$'\n'
            failed=1
        else
            rows+="| ${image} | ${tag} | ✅ 完整（${count} 個子 manifest） |"$'\n'
        fi
    done
done

{
    echo "### GHCR 標籤檢查"
    echo "| image | 標籤 | 結果 |"
    echo "|---|---|---|"
    printf '%s' "${rows}"
} >> "${GITHUB_STEP_SUMMARY}"
exit "${failed}"
