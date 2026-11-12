"""make jobs: 查看與處理背景任務 (含排程觸發的)。

    make jobs list [狀態]       最近 50 筆任務; 狀態可以是 pending、running、succeeded、failed
    make jobs retry <id>        重新排入一個失敗的任務
    make jobs run <任務名稱>    立刻排入一個任務 (手動觸發排程的任務時用)

任務執行時的 log 用 `make logs trace job-<id 的前 16 碼>` 查。
"""

from __future__ import annotations

from tools.compose import app_cli
from tools.env import fail, load_env, require_env

USAGE = (__doc__ or "").split("\n\n")[1]
STATUSES = ("pending", "running", "succeeded", "failed")


def run(_name: str, args: list[str]) -> None:
    env = load_env()
    require_env(env, "COMPOSE_PROJECT_NAME")
    valid = (
        not args
        or (args[0] == "list" and (len(args) == 1 or (len(args) == 2 and args[1] in STATUSES)))
        or (args[0] in ("retry", "run") and len(args) == 2)
    )
    if not valid:
        fail(USAGE)
    app_cli(env, "jobs", *(args or ["list"]))
