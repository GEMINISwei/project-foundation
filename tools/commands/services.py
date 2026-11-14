"""make stop / make status。

    make stop             停止服務 (容器與資料都保留)
    make status           這個專案在 Docker 上的 container 與 volume
    make status volumes   每個 volume 的容量

名稱都是 Docker 上的完整名稱, 與 `docker ps`、`docker volume ls` 看到的一致。volume 列出這個專案
所有的 (換過模式之後留下來的也算), 沒有任何容器掛著的標成 Unused。
"""

from __future__ import annotations

import json
import subprocess

from tools.compose import SERVICES, compose
from tools.env import fail, load_env, require_env

USAGE = (__doc__ or "").split("\n\n")[1]


def _table(rows: list[tuple[str, ...]]) -> list[str]:
    """每一欄從同一個位置開始, 最後一欄不補空白。"""
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]) - 1)]
    return [
        "  ".join([*(cell.ljust(width) for cell, width in zip(row, widths)), row[-1]])
        for row in rows
    ]


def _usage(used: bool) -> str:
    return "Used" if used else "Unused"


def status_lines(containers: list[tuple[str, str]], volumes: list[tuple[str, bool]]) -> list[str]:
    rows = [*containers, *((name, _usage(used)) for name, used in volumes)]
    aligned = _table(rows) if rows else []
    container_lines = aligned[: len(containers)] or ["(none)"]
    volume_lines_ = aligned[len(containers) :] or ["(none)"]
    return ["Container", *container_lines, "", "Volume", *volume_lines_]


def volume_lines(volumes: list[tuple[str, str, bool]]) -> list[str]:
    rows = [(name, size, _usage(used)) for name, size, used in volumes]
    return _table([("Volume", "Size", "Status"), *rows])


def _docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def containers(env: dict[str, str]) -> list[tuple[str, str]]:
    """(容器名稱, Docker 的狀態文字), 順序與 make doctor 相同。"""
    output = compose(
        env, "ps", "--all", "--format", "{{.Service}}\t{{.Name}}\t{{.Status}}", capture=True
    ).stdout
    order = {service: index for index, service in enumerate(SERVICES)}
    order["worker"] = len(SERVICES)
    rows = [line.split("\t") for line in output.splitlines() if line.count("\t") == 2]
    rows.sort(key=lambda row: (order.get(row[0], len(SERVICES)), row[1]))
    return [(name, status) for _, name, status in rows]


def volume_names(env: dict[str, str]) -> list[str]:
    label = f"label=com.docker.compose.project={env['COMPOSE_PROJECT_NAME']}"
    return sorted(_docker("volume", "ls", "--filter", label, "--format", "{{.Name}}").split())


def volumes(env: dict[str, str]) -> list[tuple[str, bool]]:
    # 停著的容器也算在用: 它下次啟動還會掛上同一個 volume。
    return [
        (name, bool(_docker("ps", "--all", "--quiet", "--filter", f"volume={name}")))
        for name in volume_names(env)
    ]


def volumes_with_size(env: dict[str, str]) -> list[tuple[str, str, bool]]:
    """容量要 Docker 掃過磁碟才算得出來, 資料多的時候要等幾秒。"""
    listed = json.loads(_docker("system", "df", "--verbose", "--format", "{{json .Volumes}}"))
    details = {item["Name"]: item for item in listed}
    rows = []
    for name in volume_names(env):
        item = details.get(name, {})
        rows.append((name, str(item.get("Size", "?")), int(item.get("Links", 0)) > 0))
    return rows


def run(name: str, args: list[str]) -> None:
    env = load_env()
    if name == "stop" and not args:
        # stop 而不是 down: 容器與 volume 都留著, make start 接回來。
        compose(env, "stop")
        return
    require_env(env, "COMPOSE_PROJECT_NAME")
    if name == "status" and not args:
        print("\n".join(status_lines(containers(env), volumes(env))))
    elif name == "status" and args == ["volumes"]:
        print("\n".join(volume_lines(volumes_with_size(env))))
    else:
        fail(USAGE)
