"""make gen-types: 重新產生 OpenAPI 契約與前端型別。

改了後端的 schema、路由、權限或語系之後執行, 兩份產出一起 commit。
"""

from __future__ import annotations

from tools.contract import CONTRACT, WEB_SCHEMA, generate
from tools.env import REPO_ROOT, deny_on_production, fail, load_env


def run(_name: str, args: list[str]) -> None:
    if args:
        fail("用法：make gen-types")
    deny_on_production(load_env(required=False), "make gen-types")
    generate()
    for path in (CONTRACT, WEB_SCHEMA):
        print(f"已更新：{path.relative_to(REPO_ROOT)}")
