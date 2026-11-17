"""CI 的 PR 改動檢查與總閘: 抑制註解要寫理由, 審查要看的東西列在 Job summary。

Job summary 列出新增的抑制註解、被改或刪的既有測試、被動到的防線檔案; 沒有要看的項目時只有一行。
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from support import REPO_ROOT

GIT = shutil.which("git") or "/usr/bin/git"
BASH = shutil.which("bash") or "/bin/bash"
CHECK = REPO_ROOT / ".github/scripts/check-pr-changes.py"
GATE = REPO_ROOT / ".github/scripts/ci-gate.sh"

SOURCE = "apps/api/modules/orders/service.py"
WEB_SOURCE = "apps/web/modules/orders/format.ts"
API_TEST = "apps/api/tests/modules/orders/test_service.py"
WEB_TEST = "apps/web/tests/modules/orders/format.test.ts"
TESTS = {
    API_TEST: "def test_keeps_order() -> None:\n    assert True\n",
    WEB_TEST: 'it("排序不變", () => {})\n',
}

Files = dict[str, Optional[str]]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [GIT, "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(root: Path, files: Files) -> str:
    for name, content in files.items():
        path = root / name
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", "c")
    return git(root, "rev-parse", "HEAD")


def check(tmp_path: Path, base: Files, head: Files) -> tuple[int, str, str]:
    """(結束代碼, 錯誤訊息, Job summary)。"""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    base_sha = commit(root, {**TESTS, **base})
    head_sha = commit(root, head)
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=root,
        env={
            "PATH": str(Path(GIT).parent),
            "BASE_SHA": base_sha,
            "HEAD_SHA": head_sha,
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    text = summary.read_text(encoding="utf-8") if summary.exists() else ""
    return result.returncode, result.stderr, text


def lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def test_new_plain_comment_is_allowed(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n", WEB_SOURCE: "export const x = 1\n"},
        {
            SOURCE: "x = 1\n# 對帳要照原本的順序\ny = 2\n",
            WEB_SOURCE: "export const x = 1\n// 後端已經排好\nexport const y = 2 // 含稅\n",
        },
    )

    assert (code, errors) == (0, "")


def test_suppression_without_a_reason_is_rejected(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n", WEB_SOURCE: "export const x = 1\n"},
        {
            SOURCE: 'x = 1\nkind = "bearer"  # ' + "noqa: S105\n",
            WEB_SOURCE: "export const x = 1\n// eslint-"
            + "disable-next-line no-console\nconsole.log(x)\n",
        },
    )

    assert code == 1
    assert f"{SOURCE}:2" in errors
    assert f"{WEB_SOURCE}:2" in errors


def test_suppressions_and_tool_directives_are_not_plain_comments(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n", WEB_SOURCE: "export const x = 1\n"},
        {
            SOURCE: (
                "#!/usr/bin/env python3\n"
                'kind = "bearer"  # noqa: S105  # 憑證的種類, 不是密碼\n'
                "value: int = compute()  # type: ignore[name-defined]  # 測試用的假函式\n"
                "# fmt: off\n"
                "table = [1,\n         2]\n"
                "# fmt: on\n"
            ),
            WEB_SOURCE: (
                "// eslint-disable-next-line no-console -- 啟動時只印一次\n"
                "console.log(1)\n"
                "// @ts-expect-error 型別定義還沒有這個欄位\n"
                "export const x: number = window.missing\n"
            ),
        },
    )

    assert (code, errors) == (0, "")


def test_comment_markers_inside_strings_are_ignored(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n", WEB_SOURCE: "export const x = 1\n"},
        {
            SOURCE: 'x = 1\nurl = "https://example.com/#top"\ntext = """\n# 不是註解\n"""\n',
            WEB_SOURCE: (
                "export const x = 1\n"
                'export const url = "https://example.com"\n'
                "export const text = `// ${x} /* 不是註解 */`\n"
                "export const pattern = /^https?:\\/\\/[\"']/\n"
                "export const half = x / 2\n"
            ),
        },
    )

    assert (code, errors) == (0, "")


def test_existing_comments_are_left_alone(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "# 舊的說明\nx = 1\n", WEB_SOURCE: "// 舊的說明\nexport const x = 1\n"},
        {
            SOURCE: "# 舊的說明\nx = 1\ny = 2\n",
            WEB_SOURCE: "// 舊的說明\nexport const x = 1\nexport const y = 2\n",
        },
    )

    assert (code, errors) == (0, "")


def test_docstrings_configs_and_generated_files_are_out_of_scope(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n"},
        {
            SOURCE: '"""訂單的計算。"""\n\nx = 1\n',
            "apps/web/vitest.config.ts": "// 覆蓋率門檻\nexport default {}\n",
            "apps/web/knip.ts": "// 進入點\nexport default {}\n",
            "apps/web/shared/api/schema.d.ts": "/** 產生的 */\nexport type A = string\n",
            "apps/api/migrations/versions/20260101_add.py": "# ### commands ###\nx = 1\n",
            "infra/compose/compose.yml": "# 說明\nservices: {}\n",
            ".github/scripts/deploy.sh": "# 說明\nexit 0\n",
        },
    )

    assert (code, errors) == (0, "")


def test_report_is_one_line_when_there_is_nothing_to_review(tmp_path: Path) -> None:
    code, _, summary = check(
        tmp_path,
        {SOURCE: "x = 1\n"},
        {
            SOURCE: "x = 1\ny = 2\n",
            API_TEST: TESTS[API_TEST] + "\n\ndef test_more() -> None: ...\n",
        },
    )

    assert code == 0
    assert len(lines(summary)) == 1


def test_report_lists_suppressions_changed_tests_and_protected_files(tmp_path: Path) -> None:
    added_only = "apps/api/tests/modules/orders/test_more.py"
    code, _, summary = check(
        tmp_path,
        {SOURCE: "x = 1\n", ".github/workflows/ci.yml": "name: CI\n"},
        {
            SOURCE: 'x = 1\nkind = "bearer"  # noqa: S105  # 憑證的種類, 不是密碼\n',
            WEB_TEST: 'it("排序不變", () => { expect(1).toBe(1) })\n',
            API_TEST: TESTS[API_TEST] + "\n\ndef test_more() -> None: ...\n",
            added_only: "def test_new() -> None: ...\n",
            ".github/workflows/ci.yml": "name: CI\non: push\n",
        },
    )

    assert code == 0
    assert "noqa: S105" in summary
    assert WEB_TEST in summary
    assert ".github/workflows/ci.yml" in summary
    assert API_TEST not in summary
    assert added_only not in summary


def test_report_lists_dependency_manifests_for_review(tmp_path: Path) -> None:
    manifests = {"apps/api/pyproject.toml": "[project]\n", "apps/web/package.json": "{}\n"}
    code, _, summary = check(
        tmp_path,
        {SOURCE: "x = 1\n", **manifests},
        {path: text + "\n" for path, text in manifests.items()},
    )

    assert code == 0
    assert all(path in summary for path in manifests)


def test_report_lists_deleted_test_files(tmp_path: Path) -> None:
    code, _, summary = check(tmp_path, {SOURCE: "x = 1\n"}, {WEB_TEST: None})

    assert code == 0
    assert WEB_TEST in summary


def gate(tmp_path: Path, results: dict[str, str]) -> tuple[int, str]:
    summary = tmp_path / "summary.md"
    needs = {job: {"result": result} for job, result in results.items()}
    done = subprocess.run(
        [BASH, str(GATE), "full"],
        input=json.dumps(needs),
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, summary.read_text(encoding="utf-8") if summary.exists() else ""


def test_gate_summary_lists_only_failed_jobs(tmp_path: Path) -> None:
    code, summary = gate(tmp_path, {"lint": "failure", "build": "success", "e2e": "cancelled"})

    assert code == 1
    assert "lint" in summary
    assert "failure" in summary
    assert "e2e" in summary
    assert "build" not in summary


def test_gate_summary_is_one_line_when_everything_passed(tmp_path: Path) -> None:
    code, summary = gate(tmp_path, {"lint": "success", "build": "success"})

    assert code == 0
    assert len(lines(summary)) == 1


def test_new_function_docstring_is_allowed(tmp_path: Path) -> None:
    code, errors, _ = check(
        tmp_path,
        {SOURCE: "x = 1\n"},
        {SOURCE: 'x = 1\n\n\ndef total() -> int:\n    """先算小計再加稅。"""\n    return 1\n'},
    )

    assert (code, errors) == (0, "")


def test_existing_function_docstrings_are_left_alone(tmp_path: Path) -> None:
    base = 'def total() -> int:\n    """先算小計再加稅。"""\n    return 1\n'
    code, errors, _ = check(tmp_path, {SOURCE: base}, {SOURCE: base + "\n\nx = 1\n"})

    assert (code, errors) == (0, "")


E2E_SUMMARY = REPO_ROOT / ".github/scripts/e2e-summary.py"
REPORT_URL = "https://example.com/artifacts/1"


def spec(title: str, status: str, project: str = "desktop") -> dict[str, object]:
    return {
        "title": title,
        "ok": status == "expected",
        "tests": [{"projectName": project, "status": status}],
    }


def playwright(*specs: dict[str, object]) -> dict[str, object]:
    failed = sum(1 for item in specs if not item["ok"])
    return {
        "stats": {"expected": len(specs) - failed, "unexpected": failed, "flaky": 0, "skipped": 0},
        "suites": [
            {
                "title": "users/list.spec.ts",
                "file": "users/list.spec.ts",
                "specs": list(specs[:1]),
                "suites": [{"title": "編輯", "specs": list(specs[1:])}],
            }
        ],
    }


def e2e_summary(tmp_path: Path, report: dict[str, object] | None) -> tuple[int, str]:
    results = tmp_path / "results.json"
    if report is not None:
        results.write_text(json.dumps(report), encoding="utf-8")
    summary = tmp_path / "e2e.md"
    done = subprocess.run(
        [sys.executable, str(E2E_SUMMARY), str(results)],
        env={"GITHUB_STEP_SUMMARY": str(summary), "REPORT_URL": REPORT_URL},
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, summary.read_text(encoding="utf-8") if summary.exists() else ""


def test_e2e_summary_is_one_line_with_the_report_link_when_all_pass(tmp_path: Path) -> None:
    report = playwright(spec("管理者看得到使用者清單", "expected"), spec("可以改暱稱", "expected"))
    code, summary = e2e_summary(tmp_path, report)

    assert code == 0
    assert len(lines(summary)) == 1
    assert REPORT_URL in summary


def test_e2e_summary_lists_only_failed_tests(tmp_path: Path) -> None:
    report = playwright(
        spec("管理者看得到使用者清單", "expected"),
        spec("不能停用自己", "unexpected", project="mobile"),
    )
    code, summary = e2e_summary(tmp_path, report)

    assert code == 0
    assert "不能停用自己" in summary
    assert "mobile" in summary
    assert "users/list.spec.ts" in summary
    assert "管理者看得到使用者清單" not in summary
    assert REPORT_URL in summary


def test_e2e_summary_says_so_when_there_are_no_results(tmp_path: Path) -> None:
    code, summary = e2e_summary(tmp_path, None)

    assert code == 0
    assert len(lines(summary)) == 1


def test_report_does_not_list_test_files_whose_only_changes_are_comments(tmp_path: Path) -> None:
    commented = "def test_keeps_order() -> None:\n    # 舊的說明\n    assert True\n"
    code, errors, summary = check(
        tmp_path,
        {SOURCE: "x = 1\n", API_TEST: commented},
        {API_TEST: TESTS[API_TEST]},
    )

    assert (code, errors) == (0, "")
    assert "改掉既有內容的測試檔" not in summary
