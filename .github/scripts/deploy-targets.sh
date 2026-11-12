#!/usr/bin/env bash
#
# 從 repo 的 environment 名稱挑出這次要部署的組 (environment 名稱一行一個從 stdin 讀進來,
# deploy.yml 從 GitHub API 取得):
#
#   deploy-targets.sh select <組名>...   要部署的 environment, 每行 `<組名><TAB><environment>`
#   deploy-targets.sh others <組名>...   repo 裡有、但這次沒被選到的組, 一行一個
#
# 組名 = environment 名稱第一個 `-` 之前的部分: production 組是 `production` 與 `production-*`。
# 不用 `production*` 的萬用比對: 那會把 `productionx` 也算進來。比對不分大小寫, 跟 GitHub 一樣。
#
# select 時任何一組找不到 environment 就整個失敗、一套都不部署: 組名打錯不能變成「其他組照常
# 部署, 結果是綠的」, 漏掉的那組要等到有人發現版本不對才知道。
#
# 要能在 macOS 內建的 bash 3.2 跑 (它的測試也會在本機執行), 所以不用 ${var,,}、mapfile
# 與關聯陣列。
set -euo pipefail

usage() {
    echo "用法：deploy-targets.sh select|others <組名>... < environment 名稱清單" >&2
    exit 2
}

mode="${1:-}"
case "${mode}" in
    select|others) shift ;;
    *) usage ;;
esac

# 組名也是 image 的標籤 (ghcr.io/...-api:<組名>), 所以只收標籤合法、而且不含分隔字元 `-` 的寫法。
wanted=" "
for target in "$@"; do
    if ! [[ "${target}" =~ ^[a-z0-9][a-z0-9_.]*$ ]]; then
        echo "組名格式不對：「${target}」（小寫英數與 . _，例如 production、staging）" >&2
        exit 1
    fi
    wanted="${wanted}${target} "
done
if [ "${wanted}" = " " ]; then
    echo "沒有指定任何組" >&2
    exit 1
fi

pairs=()
available=" "
while IFS= read -r name || [ -n "${name}" ]; do
    [ -n "${name}" ] || continue
    lower="$(printf '%s' "${name}" | tr '[:upper:]' '[:lower:]')"
    group="${lower%%-*}"
    pairs+=("${group}"$'\t'"${name}")
    case "${available}" in *" ${group} "*) ;; *) available="${available}${group} " ;; esac
done

sorted_words() {
    # shellcheck disable=SC2086 # 刻意依空白拆成多個字
    [ -z "${1// /}" ] || printf '%s\n' $1 | LC_ALL=C sort -u
}

if [ "${mode}" = others ]; then
    for group in $(sorted_words "${available}"); do
        case "${wanted}" in *" ${group} "*) ;; *) echo "${group}" ;; esac
    done
    exit 0
fi

missing=()
for target in $(sorted_words "${wanted}"); do
    case "${available}" in *" ${target} "*) ;; *) missing+=("${target}") ;; esac
done
if [ "${#missing[@]}" -gt 0 ]; then
    if [ "${available}" = " " ]; then
        echo "repo 還沒有任何 environment，請先在 Settings → Environments 建立（例如 production）" >&2
    else
        echo "找不到這些組的 environment：${missing[*]}（現有的組：$(sorted_words "${available}" | paste -sd ' ' -)）" >&2
    fi
    exit 1
fi

for pair in "${pairs[@]}"; do
    case "${wanted}" in *" ${pair%%$'\t'*} "*) echo "${pair}" ;; esac
done | LC_ALL=C sort
