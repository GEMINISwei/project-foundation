#!/usr/bin/env bash
#
# 這次 CI 要跑哪些檢查 (ci.yml 的 changes job):
#
#   git diff --name-only <base> <head> | ci-mode.sh <事件名稱>
#
# 印出 docs 或 full。PR 改的檔案全部是 Markdown 時是 docs: 文件不進 image、不影響 build,
# 只跑單元測試 (連結、ADR 與 skill 的格式在裡面)。其餘一律 full:
# - 白名單: 全部是 .md 才放寬, 新的檔案類型預設跑完整的檢查。
# - 不是 PR 的事件 (push main、deploy.yml 的 workflow_call、手動執行): 部署靠 main 的 CI 結果。
# - 改動清單是空的: 當成拿不到清單, 不當成「沒改東西」。
set -euo pipefail

[ "$#" -eq 1 ] || { echo "用法：git diff --name-only … | ci-mode.sh <事件名稱>" >&2; exit 2; }

if [ "$1" != "pull_request" ]; then
    echo full
    exit 0
fi

files="$(grep -v '^$' || true)"
if [ -z "${files}" ] || printf '%s\n' "${files}" | grep -qv '\.md$'; then
    echo full
else
    echo docs
fi
