"""make logs: 看各服務的 log, 或用 request id 把一次請求在各層的紀錄撈出來。

    make logs                     跟著看全部服務
    make logs api                 只看一個服務 (nginx、web、api、worker、postgres、migrate)
    make logs trace <request-id>  這次請求在 nginx、web、api、worker 的所有紀錄, 依時間排序
    make logs errors [分鐘]       最近 N 分鐘 (預設 60) 的錯誤與警告

request id 顯示在錯誤畫面上, 也在回應的 X-Request-ID 標頭裡。
LOG_DRIVER=journald 時讀主機的 journald, 重建容器之前的紀錄也查得到; 帳號要在 systemd-journal 群組。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

from tools.compose import SERVICES, compose, containers, log_driver
from tools.env import fail, load_env

USAGE = (__doc__ or "").split("\n\n")[1]
TRACED_SERVICES = ("nginx", "web", "api", "worker")
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
# api 與 worker 寫 JSON (level 欄位), nginx 的錯誤 log 帶 [error]。
PROBLEM = re.compile(r'"level": ?"(warning|error|critical)"|\[(error|crit|alert|emerg)\]')
# journalctl 沒有權限時照樣以 0 結束, 只在 stderr 留這兩種提示 (LC_ALL=C 的原文)。
JOURNAL_DENIED = ("not seeing messages", "insufficient permissions")


def journal_problem() -> str:
    """讀不到 journald 的原因; 讀得到回傳空字串。讀不到與「沒有紀錄」要分得出來。"""
    if shutil.which("journalctl") is None:
        return "LOG_DRIVER=journald，但這台機器沒有 journalctl"
    result = subprocess.run(
        ["journalctl", "--no-pager", "-n", "0"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode != 0 or any(hint in result.stderr for hint in JOURNAL_DENIED):
        return (
            "這個帳號讀不到系統的 journal：用有 sudo 的帳號執行 "
            "`sudo usermod -aG systemd-journal <這個帳號>`，重新登入後再試"
        )
    return ""


def read_logs(env: dict[str, str], service: str, since: str | None) -> list[str]:
    """一個服務所有容器的 log, 每行前面帶 docker 的時間戳 (RFC 3339, 可以直接字串排序)。"""
    lines: list[str] = []
    for name in containers(env, service):
        if log_driver(env) == "journald":
            command = [
                "journalctl",
                f"CONTAINER_NAME={name}",
                "--no-pager",
                "-o",
                "short-iso-precise",
            ]
        else:
            command = ["docker", "logs", "--timestamps", name]
        command += ["--since", since] if since else []
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        lines += (result.stdout + result.stderr).splitlines()
    return lines


def search(env: dict[str, str], match: re.Pattern[str], since: str | None) -> int:
    found: list[tuple[str, str, str]] = []
    for service in TRACED_SERVICES:
        for line in read_logs(env, service, since):
            if match.search(line):
                timestamp, _, rest = line.partition(" ")
                found.append((timestamp, service, rest))
    for timestamp, service, rest in sorted(found):
        print(f"{timestamp} {service:<6} {rest}")
    return len(found)


def run(_name: str, args: list[str]) -> None:
    env = load_env()
    searching = bool(args) and args[0] in ("trace", "errors")
    if searching and log_driver(env) == "journald" and (problem := journal_problem()):
        fail(problem)
    if not args:
        compose(env, "logs", "--follow", "--tail", "100")
    elif args[0] == "trace" and len(args) == 2:
        if not REQUEST_ID.match(args[1]):
            fail("request id 的格式不對（英數與 -，8 到 64 個字元）")
        if search(env, re.compile(re.escape(args[1])), None) == 0:
            print("找不到這個 request id 的紀錄（log 可能已經輪替，或 id 不完整）", file=sys.stderr)
    elif args[0] == "errors" and len(args) <= 2:
        minutes = args[1] if len(args) == 2 else "60"
        if not minutes.isdigit():
            fail(USAGE)
        if (
            search(
                env, PROBLEM, f"{minutes}m" if log_driver(env) != "journald" else f"-{minutes}min"
            )
            == 0
        ):
            print(f"最近 {minutes} 分鐘沒有錯誤或警告")
    elif len(args) == 1 and args[0] in SERVICES:
        compose(env, "logs", "--follow", "--tail", "200", args[0])
    else:
        fail(USAGE)
