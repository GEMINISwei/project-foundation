"""這次請求 (或這次任務) 的情境: 追蹤 id、操作者、來源 IP。

用 ContextVar 而不是一路傳參數: 需要它們的是 log、AUDIT 與錯誤回應, 不該滲透進每一層的簽名。
值同時綁進 structlog, 之後每一行 log 都自動帶上。
"""

import re
import secrets
from contextvars import ContextVar

import structlog

# 值可能來自外部標頭而且會寫進 log: 限制長度與字元, 偽造不出另一行紀錄。
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SAFE_IP = re.compile(r"^[0-9A-Fa-f:.]{1,45}$")

#: "-" 代表不在請求裡 (啟動流程、CLI)。
request_id: ContextVar[str] = ContextVar("request_id", default="-")
user_id: ContextVar[str] = ContextVar("user_id", default="-")
client_ip: ContextVar[str] = ContextVar("client_ip", default="-")


def new_trace_id() -> str:
    """16 個字元: 夠獨特, 而且會出現在每一行 log 上, 越短越好。"""
    return secrets.token_hex(8)


def begin(*, trace_id: str | None, ip: str | None = None) -> str:
    """設定這次請求或任務的情境, 回傳實際使用的追蹤 id。

    上游送來的 id 合格就沿用 (nginx、web、api 才串得起來), 否則產生新的。
    """
    resolved = trace_id if trace_id and _SAFE_REQUEST_ID.match(trace_id) else new_trace_id()
    resolved_ip = ip if ip and _SAFE_IP.match(ip) else "-"
    request_id.set(resolved)
    client_ip.set(resolved_ip)
    user_id.set("-")
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=resolved)
    return resolved


def set_user(value: str) -> None:
    user_id.set(value)
    structlog.contextvars.bind_contextvars(user_id=value)
