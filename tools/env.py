"""repo 根目錄、.env 的讀取與共用的小工具。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

MODES = ("development", "production")


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_env_file(path: Path) -> dict[str, str]:
    """與 `docker compose --env-file` 相同的解讀: compose 也直接讀這份, 兩邊不一致的話
    同一個變數在指令與容器裡會是不同的值。"""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            # 行內註解要「空白 + #」; 貼在最前面的 # 是值的一部分。
            for separator in (" #", "\t#"):
                if separator in value:
                    value = value.split(separator, 1)[0].rstrip()
        values[key] = value
    return values


def load_env(*, required: bool = True) -> dict[str, str]:
    """讀 .env 並放進 os.environ (.env 優先, 子行程才拿得到同一組值)。"""
    if not ENV_FILE.exists():
        if required:
            fail("找不到 .env，請先執行 make init dev|prod")
        return {}
    values = parse_env_file(ENV_FILE)
    os.environ.update(values)
    return values


def require_env(env: dict[str, str], *names: str) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        fail(f"缺少環境變數：{' '.join(missing)}（請確認 .env，或重新執行 make init dev|prod）")


def require_mode(env: dict[str, str]) -> str:
    mode = env.get("MODE", "")
    if mode not in MODES:
        fail(f".env 的 MODE 必須是 development 或 production（目前是「{mode}」）")
    return mode


def deny_on_production(env: dict[str, str], command: str) -> None:
    """只屬於開發機的指令在正式主機上拒絕執行。防手誤, 不是權限控制。"""
    if env.get("MODE") == "production":
        fail(f"正式環境（MODE=production）不能執行 {command}")


def require_tool(name: str, hint: str = "") -> None:
    if shutil.which(name) is None:
        fail(f"缺少 {name}{'：' + hint if hint else ''}")


def confirm(question: str) -> None:
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        fail("已取消")


def app_version() -> str:
    """這份 checkout 的版號 (不帶 v)。只有這個值跟著發版。"""
    text = (REPO_ROOT / "apps/api/app/version.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("APP_VERSION = "):
            return line.split("=", 1)[1].strip().strip('"')
    fail("在 apps/api/app/version.py 找不到 APP_VERSION")
