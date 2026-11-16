#!/usr/bin/env python3
"""E2E 的 Job summary: REPORT_URL=… .github/scripts/e2e-summary.py <Playwright 的 JSON 結果>

ci.yml 的 e2e job 呼叫。全部通過時只有一行加上報告與截圖的連結, 有失敗時列出失敗的測試。
沒有結果檔 (測試沒跑起來) 時寫一行說明。結束代碼一律是 0: 過不過由跑測試的那一步決定。
要能在 Python 3.9 上跑 (macOS 內建)。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

PASSED = ("expected", "skipped", "flaky")


def failures(suite: dict[str, Any], file: str, titles: list[str]) -> list[tuple[str, str, str]]:
    rows = []
    for spec in suite.get("specs") or []:
        for test in spec.get("tests") or []:
            if test.get("status") not in PASSED:
                name = " › ".join([*titles, spec.get("title", "")]).replace("|", "\\|")
                rows.append((file, name, test.get("projectName", "")))
    for child in suite.get("suites") or []:
        rows += failures(child, file, [*titles, child.get("title", "")])
    return rows


def summary(results: Path, url: str) -> str:
    link = f"（[報告與截圖]({url})）" if url else ""
    if not results.exists():
        return f"E2E 沒有產生結果，測試可能沒有跑起來{link}。\n"
    report = json.loads(results.read_text(encoding="utf-8"))
    rows = [
        row
        for suite in report.get("suites") or []
        for row in failures(suite, suite.get("file") or suite.get("title", ""), [])
    ]
    if not rows:
        passed = report.get("stats", {}).get("expected", 0)
        return f"E2E {passed} 個測試全部通過{link}。\n"
    lines = [f"### E2E 沒有通過的測試{link}", "", "| 檔案 | 測試 | 裝置 |", "|---|---|---|"]
    lines += [f"| {file} | {name} | {device} |" for file, name, device in rows]
    return "\n".join([*lines, ""])


def main() -> int:
    text = summary(Path(sys.argv[1]), os.environ.get("REPORT_URL", ""))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
