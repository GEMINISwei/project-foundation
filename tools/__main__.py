"""指令的進入點: python3 -m tools <指令> [參數…]。"""

from __future__ import annotations

import importlib
import io
import os
import subprocess
import sys

# 指令名稱 → (模組, 一行說明)。順序就是 make help 的顯示順序。
COMMANDS: dict[str, tuple[str, str]] = {
    "init": ("init", "建立 .env 並安裝相依：make init dev|prod"),
    "start": ("start", "啟動服務（會先跑 migration）；開發機可加 lan 對區網開放"),
    "stop": ("services", "停止服務（資料保留）"),
    "status": ("services", "各容器的狀態與健康檢查結果"),
    "logs": ("logs", "看 log：make logs [服務]｜make logs trace <request-id>｜make logs errors"),
    "doctor": ("doctor", "檢查這台機器與執行中的服務，列出所有問題"),
    "db": ("db", "資料庫與帳號：psql、superuser、revoke-sessions、migration、reset"),
    "jobs": ("jobs", "背景任務：list、retry、run"),
    "backup": ("backup", "備份與還原：make backup｜prune｜restore db|uploads"),
    "check": (
        "check",
        "檢查與測試：lint、types、contract、migrations、api-test、integration、web-test、build",
    ),
    "gen-types": ("gen_types", "重新產生 OpenAPI 契約與前端型別"),
    "e2e": ("e2e", "瀏覽器測試：up、test、grep、down、check"),
    "release": ("release", "準備發版：make release <版號>"),
}


def prepare_streams() -> None:
    """讓指令在 ssh、CI 這類沒有終端機的地方, 行為與在終端機裡一樣。"""
    # 輸出被接走時 Python 整塊緩衝, 子行程的輸出會跑到自己的訊息前面。
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(line_buffering=True)
    if sys.stdin is None or sys.stdin.isatty():
        return
    # 子行程不繼承 stdin: 部署腳本經 ssh 的 stdin 交給 bash 逐行執行, 被子行程 (docker compose
    # run、docker run -i) 讀走的話, 後面的步驟不會執行也不會報錯。自己的確認提示改讀另一個
    # 不會被繼承的 fd; 真的要餵資料給子行程的地方都明確指定 stdin。
    # 這個檔案物件跟著行程活到結束, 不關閉。
    sys.stdin = open(os.dup(0), encoding=sys.stdin.encoding, errors=sys.stdin.errors)
    with open(os.devnull) as devnull:
        os.dup2(devnull.fileno(), 0)


def print_help() -> None:
    print("用法：make <指令> [參數…]\n")
    for name, (_, summary) in COMMANDS.items():
        print(f"  {name:<10} {summary}")
    print("\n子指令的用法：make <指令> help")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("help", "-h", "--help"):
        print_help()
        return 0
    name, args = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"沒有這個指令：{name}\n", file=sys.stderr)
        print_help()
        return 1
    if args in (["help"], ["-h"], ["--help"]):
        print(
            (importlib.import_module(f"tools.commands.{COMMANDS[name][0]}").__doc__ or "").strip()
        )
        return 0
    module = importlib.import_module(f"tools.commands.{COMMANDS[name][0]}")
    try:
        module.run(name, args)
    except subprocess.CalledProcessError as error:
        # 子行程的錯誤訊息已經印在上面, 不再附一段 Python 的 traceback。
        return error.returncode or 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    prepare_streams()
    sys.exit(main(sys.argv[1:]))
