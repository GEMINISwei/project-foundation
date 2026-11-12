"""指令的進入點: python3 -m tools <指令> [參數…]。"""

from __future__ import annotations

import importlib
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
    sys.exit(main(sys.argv[1:]))
