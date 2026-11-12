#!/usr/bin/env bash
#
# 連主機前的準備 (deploy.yml 的 migration-check 與 deploy 共用):
#
#   deploy-ssh.sh <environment>   從環境變數讀 DEPLOY_HOST、DEPLOY_USER、DEPLOY_PATH、
#                                 DEPLOY_SSH_KEY、DEPLOY_KNOWN_HOSTS
#
# 剛建好、還沒填 secrets 的 environment 在這裡就停, 不必等 SSH 報出看不懂的錯; 缺的時候什麼都不寫。
# 都有的話寫出 ~/.ssh/deploy_key 與 ~/.ssh/known_hosts。
# 主機指紋事先登記, 不用 StrictHostKeyChecking=no: 那等於誰冒充主機都收得到 token。
#
# 要能在 macOS 內建的 bash 3.2 跑 (它的測試也會在本機執行)。
set -euo pipefail

[ "$#" -eq 1 ] || { echo "用法：deploy-ssh.sh <environment>" >&2; exit 2; }

missing=""
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_PATH DEPLOY_SSH_KEY DEPLOY_KNOWN_HOSTS; do
    [ -n "${!name:-}" ] || missing="${missing} ${name}"
done
if [ -n "${missing}" ]; then
    echo "environment $1 缺少 secrets：${missing# }" >&2
    exit 1
fi

install -m 700 -d ~/.ssh
(umask 077 && printf '%s\n' "${DEPLOY_SSH_KEY}" > ~/.ssh/deploy_key)
chmod 600 ~/.ssh/deploy_key
printf '%s\n' "${DEPLOY_KNOWN_HOSTS}" > ~/.ssh/known_hosts
