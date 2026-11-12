"""make stop / make status。"""

from __future__ import annotations

from tools.compose import compose
from tools.env import fail, load_env


def run(name: str, args: list[str]) -> None:
    if args:
        fail(f"用法：make {name}")
    env = load_env()
    if name == "stop":
        # stop 而不是 down: 容器與 volume 都留著, make start 接回來。
        compose(env, "stop")
    else:
        compose(env, "ps", "--all", "--format", "table {{.Service}}\t{{.Status}}")
