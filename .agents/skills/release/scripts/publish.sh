#!/usr/bin/env bash
#
# 發布 release, 會直接觸發部署: publish.sh <版號> [--prerelease]
#
#   publish.sh 0.1.0 --prerelease   建立 pre-release, 部署到 PRE_RELEASE_TARGETS
#   publish.sh 0.1.0                建立正式版; 已經是 pre-release 時改成正式版, 部署到 PUBLISH_TARGETS
#
# agent 只能用這個固定寫法執行: Claude 的 permissions.ask 與 Codex 的 .codex/rules/ 讓它一定跳出確認,
# 直接下 gh release 或換寫法呼叫會被 .agents/hooks/guard_commands.py 擋下 (docs/foundation/hooks-and-skills.md)。
# 執行前先用 preview.sh 給使用者看過。
set -euo pipefail

# shellcheck source=.agents/skills/release/scripts/plan.sh
source "$(dirname "$0")/plan.sh"

mode=release
[ "${2:-}" = --prerelease ] && mode=prerelease
plan_release "${1:-}" "${mode}"
trap 'rm -f "${NOTES_FILE}"' EXIT

if [ "${ACTION}" = promote ]; then
    gh release edit "${TAG}" --prerelease=false
else
    prerelease=false
    [ "${mode}" = prerelease ] && prerelease=true
    gh release create "${TAG}" --target "${TARGET}" --title "${TAG}" --notes-file "${NOTES_FILE}" \
        --prerelease="${prerelease}"
fi
echo "已發布 ${TAG}，Deploy workflow 會開始部署。"
