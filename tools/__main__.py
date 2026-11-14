"""指令的進入點: python3 -m tools <指令> [參數…]。"""

from __future__ import annotations

import importlib
import io
import os
import subprocess
import sys

from tools.env import ENV_FILE, app_version, deny_on_production, parse_env_file

# 指令名稱 → (模組, 一行說明)。順序就是 make help 的顯示順序。
COMMANDS: dict[str, tuple[str, str]] = {
    "init": ("init", "建立 .env 並安裝相依：make init dev|prod"),
    "start": ("start", "啟動服務（會先跑 migration）；開發機可加 lan 對區網開放"),
    "stop": ("services", "停止服務（資料保留）"),
    "status": ("services", "Docker 上的 container 與 volume；make status volumes 看容量"),
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
    "pipeline": ("pipeline", "部署流程呼叫的步驟"),
}
#: 只屬於開發機的指令: 正式環境的 help 不列, 下了也會被拒絕。兩件事用同一份清單。
DEVELOPMENT_ONLY = ("check", "gen-types", "e2e", "release")
#: 給自動化呼叫的, 任何狀態下都不列在 help 裡。
HIDDEN = ("pipeline",)
#: 子指令的說明裡帶這個標記的行, 在正式環境不顯示。
DEVELOPMENT_ONLY_MARK = "僅開發環境"
PRODUCTION_SUMMARIES = {
    "db": "資料庫與帳號：psql、superuser、revoke-sessions",
    "start": "啟動服務（會先跑 migration）",
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


def current_env() -> dict[str, str] | None:
    """這份 checkout 的 .env; 還沒有 (沒跑過 make init) 是 None。"""
    return parse_env_file(ENV_FILE) if ENV_FILE.exists() else None


def is_production(env: dict[str, str] | None) -> bool:
    return bool(env) and env.get("MODE") == "production"


def visible_commands(env: dict[str, str] | None) -> list[tuple[str, str]]:
    """這個狀態下 make help 要列的指令。

    只決定「列不列」: 沒列出來的指令照樣能執行 (CI 沒有 .env 也要跑 make check),
    會不會被拒絕由 `main()` 與各指令自己的檢查決定。
    """
    if env is None:
        return [("init", COMMANDS["init"][1])]
    production = is_production(env)
    mode = "prod" if production else "dev"
    listed = []
    for name, (_, summary) in COMMANDS.items():
        if name in HIDDEN or (production and name in DEVELOPMENT_ONLY):
            continue
        if name == "init":
            summary = f"補上 .env.example 新增的變數：make init {mode}"
        elif production:
            summary = PRODUCTION_SUMMARIES.get(name, summary)
        listed.append((name, summary))
    return listed


def command_help(name: str, env: dict[str, str] | None) -> str:
    """`make <指令> help`: 指令模組的說明; 正式環境不顯示只屬於開發環境的子指令。"""
    text = (importlib.import_module(f"tools.commands.{COMMANDS[name][0]}").__doc__ or "").strip()
    if not is_production(env):
        return text
    return "\n".join(line for line in text.splitlines() if DEVELOPMENT_ONLY_MARK not in line)


def print_help(env: dict[str, str] | None) -> None:
    if env is None:
        print("還沒有 .env：先建立它，其他指令之後才會列出來。\n")
    else:
        name = env.get("SYSTEM_NAME") or env.get("COMPOSE_PROJECT_NAME", "")
        print(f"目前：{env.get('MODE', '')}（{name} v{app_version()}）\n")
    print("用法：make <指令> [參數…]\n")
    for name, summary in visible_commands(env):
        print(f"  {name:<10} {summary}")
    if env is not None:
        print("\n子指令的用法：make <指令> help")
    if is_production(env):
        print(f"開發用的指令（{'、'.join(DEVELOPMENT_ONLY)}）在正式環境不能執行，這裡不列出。")


def main(argv: list[str]) -> int:
    env = current_env()
    if not argv or argv[0] in ("help", "-h", "--help"):
        print_help(env)
        return 0
    name, args = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"沒有這個指令：{name}\n", file=sys.stderr)
        print_help(env)
        return 1
    if name in DEVELOPMENT_ONLY:
        deny_on_production(env or {}, f"make {name}")
    if args in (["help"], ["-h"], ["--help"]):
        print(command_help(name, env))
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
