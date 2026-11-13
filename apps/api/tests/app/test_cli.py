"""在主機上下的管理指令。"""

import io
import logging
import sys

import pytest

from app import cli
from shared.db.session import start_engine, stop_engine
from shared.logging import configure_logging
from tests.helpers import PASSWORD, scalar

pytestmark = pytest.mark.integration


async def test_account_commands_hide_audit_log_but_keep_record(db_ready, monkeypatch, capsys):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", root.handlers)
    monkeypatch.setattr(root, "level", root.level)
    configure_logging(json_output=True)
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"Root\nroot\n{PASSWORD}\n"))
    # 指令像在主機上一樣自己啟動與關閉引擎: 先關掉測試的那一個 (不然它的連線沒人關), 跑完再開回來。
    await stop_engine()
    try:
        await cli.cmd_superuser([])
        await cli.cmd_revoke_sessions([])
    finally:
        start_engine()

    output = capsys.readouterr().out
    assert "已建立超級管理者：root" in output
    assert "audit" not in output
    events = await scalar(
        "SELECT count(*) FROM audit_logs"
        " WHERE event IN ('superuser_created', 'sessions_revoked_all')"
    )
    assert events == 2
