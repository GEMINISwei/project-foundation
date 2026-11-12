#!/usr/bin/env bash
#
# preview.sh 與 publish.sh 共用: 從合併後的 origin/main 算出這次發布要做什麼, 並印出來。
#
# 被 source 的檔案, 不寫 `set -euo pipefail`: 那是呼叫端的決定。

require_version_format() {
    if ! [[ "$1" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
        echo "版號要是 X.Y.Z（每段是數字，不可有前導零），例如 0.1.0" >&2
        return 1
    fi
}

require_untagged_version() {
    if git rev-parse --quiet --verify "refs/tags/v$1" > /dev/null; then
        echo "tag v$1 已經存在" >&2
        return 1
    fi
}

# version_at_ref <ref>: 那個 ref 上的 APP_VERSION。
version_at_ref() {
    local version
    version="$(git show "$1:apps/api/app/version.py" 2> /dev/null | sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p')"
    if [ -z "${version}" ]; then
        echo "$1 上的 apps/api/app/version.py 找不到 APP_VERSION" >&2
        return 1
    fi
    printf '%s\n' "${version}"
}

# changelog_section <版號> <CHANGELOG 檔>: 那一版的段落內容 (去掉頭尾空行)。
changelog_section() {
    local section
    section="$(awk -v heading="## [$1]" '
        $0 == heading { found = 1; next }
        found && /^## \[/ { exit }
        found { lines[++n] = $0 }
        END {
            first = 1; while (first <= n && lines[first] !~ /[^[:space:]]/) first++
            last = n; while (last >= first && lines[last] !~ /[^[:space:]]/) last--
            for (i = first; i <= last; i++) print lines[i]
        }' "$2")"
    if [ -z "${section}" ]; then
        echo "CHANGELOG.md 沒有 [$1] 的段落，或段落是空的" >&2
        return 1
    fi
    printf '%s\n' "${section}"
}

# release_action <目前的狀態: none|prerelease|release> <這次要發的: prerelease|release>
release_action() {
    case "$1" in
        none) echo create ;;
        prerelease)
            if [ "$2" = prerelease ]; then
                echo "這一版已經是 pre-release；要改成正式版就不要帶 --prerelease" >&2
                return 1
            fi
            echo promote
            ;;
        *)
            echo "這一版已經發布成正式版；重新部署請在 Actions 的 Deploy 按 Run workflow" >&2
            return 1
            ;;
    esac
}

# plan_release <版號> <prerelease|release>: 設定 TAG、TARGET、ACTION、NOTES_FILE 並印出摘要。
# 任何一項不對就回傳非 0, 什麼都不做。
plan_release() {
    local version="$1" mode="$2" on_main state targets_var
    require_version_format "${version}" || return 1
    git fetch --quiet --tags origin || { echo "無法 fetch origin" >&2; return 1; }

    # tag 必須打在版號已經合併進去的 commit 上: deploy.yml 會檢查 tag 等於 v<APP_VERSION>。
    TARGET="$(git rev-parse origin/main)"
    on_main="$(version_at_ref origin/main)" || return 1
    if [ "${on_main}" != "${version}" ]; then
        echo "origin/main 的 APP_VERSION 是 ${on_main}，不是 ${version}：發版的 PR 還沒合併？" >&2
        return 1
    fi

    TAG="v${version}"
    state="$(gh release list --limit 1000 --json tagName,isPrerelease \
        --jq ".[] | select(.tagName == \"${TAG}\") | if .isPrerelease then \"prerelease\" else \"release\" end")"
    ACTION="$(release_action "${state:-none}" "${mode}")" || return 1
    if [ "${ACTION}" = create ]; then
        require_untagged_version "${version}" || return 1
    fi

    NOTES_FILE="$(mktemp)"
    changelog_section "${version}" <(git show origin/main:CHANGELOG.md) > "${NOTES_FILE}" || return 1

    # 部署哪些組由 repo 的 Variables 決定 (deploy.yml): pre-release 給 PRE_RELEASE_TARGETS, 其餘給 PUBLISH_TARGETS。
    targets_var=PUBLISH_TARGETS
    [ "${mode}" = prerelease ] && targets_var=PRE_RELEASE_TARGETS

    if [ "${ACTION}" = promote ]; then
        echo "動作：把 pre-release ${TAG} 改成正式版"
    elif [ "${mode}" = prerelease ]; then
        echo "動作：建立 pre-release ${TAG}"
    else
        echo "動作：建立正式版 ${TAG}"
    fi
    echo "commit：$(git log -1 --format='%h %s' "${TAG}" 2> /dev/null || git log -1 --format='%h %s' "${TARGET}")"
    echo "部署的組（${targets_var}）：$(gh variable get "${targets_var}" 2> /dev/null || echo '未設定，不會部署任何一組')"
    echo "內文："
    sed 's/^/  /' "${NOTES_FILE}"
}
