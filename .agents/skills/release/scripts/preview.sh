#!/usr/bin/env bash
#
# 列出這次發布會做什麼, 不改任何東西: preview.sh <版號> [--prerelease]
#
# 發布會直接部署, 所以先用這支把 tag、commit、部署的組與內文給使用者看, 同意後才執行 publish.sh。
set -euo pipefail

# shellcheck source=.agents/skills/release/scripts/plan.sh
source "$(dirname "$0")/plan.sh"

mode=release
[ "${2:-}" = --prerelease ] && mode=prerelease
plan_release "${1:-}" "${mode}"
rm -f "${NOTES_FILE}"
