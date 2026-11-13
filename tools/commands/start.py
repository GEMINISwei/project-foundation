"""make start [lan]: 啟動整套服務。

啟動順序是 postgres → migrate → api、worker → web → nginx, 全部就緒而且入口打得通才算成功。

正式環境升版時新舊程式不會同時服務: 映像檔先備好 → 檢查 nginx 設定 → 停掉對外入口與舊的
web、api、worker (等進行中的請求與任務做完) → migrate → 啟動新版。migrate 或啟動失敗時對外入口
維持關閉: 寧可停在維護狀態, 也不讓不確定的版本接流量。
"""

from __future__ import annotations

import os
import subprocess

from tools.compose import (
    LONG_RUNNING,
    WRITERS,
    check_capacity,
    compose,
    describe,
    entry_responds,
    wait_until_ready,
)
from tools.env import REPO_ROOT, app_version, fail, load_env, require_env, require_mode

USAGE = "用法：make start [lan]（lan 僅限開發機，讓區網內的裝置連進來）"
MAINTENANCE_HINT = (
    "對外入口維持關閉（維護狀態）。修正後重新執行 make start；"
    "要退回上一版見 docs/foundation/operations.md 的「回滾」"
)


def require_release_checkout() -> None:
    """正式環境只從發版的 tag 啟動, 避免上線沒發版、沒經過 CI 的程式碼。"""
    version = app_version()

    def rev(ref: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--quiet", "--verify", ref],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()

    tagged, head = rev(f"refs/tags/v{version}^{{commit}}"), rev("HEAD")
    if not tagged or tagged != head:
        fail(
            f"正式環境只能從發版的 tag 啟動：HEAD 要停在 v{version}\n"
            f"  git fetch --tags && git checkout v{version}"
        )


def prepare_images(env: dict[str, str], extra: dict[str, str]) -> None:
    """映像檔在停服務之前備好: 下載或建置的時間不算進停機時間, 失敗時線上也還沒動。"""
    # 部署流程會匯出 API_IMAGE 與 WEB_IMAGE, 這時改從 registry 拉, 不在主機上建置。
    from_registry = bool(os.environ.get("API_IMAGE") or os.environ.get("WEB_IMAGE"))
    if from_registry:
        if not (os.environ.get("API_IMAGE") and os.environ.get("WEB_IMAGE")):
            fail("API_IMAGE 與 WEB_IMAGE 要一起給")
        extra["IMAGE_PULL_POLICY"] = "always"
    compose(env, "pull" if from_registry else "build", extra_env=extra)


def startup_problem(env: dict[str, str]) -> str:
    """啟動之後哪裡不對; 全部正常回傳空字串。"""
    pending = wait_until_ready(env, LONG_RUNNING)
    if pending:
        return f"服務沒有就緒：{describe(pending)}"
    if not entry_responds(env):
        return f"入口沒有回應：http://127.0.0.1:{env['SYSTEM_PORT']}/healthz"
    return ""


def run(_name: str, args: list[str]) -> None:
    if args not in ([], ["lan"]):
        fail(USAGE)
    lan = args == ["lan"]
    env = load_env()
    require_env(env, "COMPOSE_PROJECT_NAME", "SYSTEM_PORT")
    mode = require_mode(env)
    check_capacity(env)
    if lan and mode != "development":
        fail("正式環境不能用 lan：nginx 信任上一層送來的 X-Real-IP，對外開放就能冒充任何 IP")
    extra = {"DEV_BIND_ADDRESS": "0.0.0.0" if lan else "127.0.0.1"}  # noqa: S104

    production = mode == "production"
    if production:
        require_release_checkout()
        prepare_images(env, extra)

    check = compose(
        env, "run", "--rm", "--no-deps", "-T", "nginx", "nginx", "-t",
        check=False, capture=True, extra_env=extra,
    )  # fmt: skip
    if check.returncode != 0:
        fail(f"{check.stdout}{check.stderr}\nnginx 設定檢查失敗，沒有啟動；線上的服務維持原樣")

    if production:
        # 從這裡開始是維護狀態: 舊程式不能配新的資料表結構, 所以先全部停下來。
        print("進入維護狀態：停止對外入口與舊版服務（等進行中的請求與任務做完）")
        compose(env, "stop", *WRITERS, extra_env=extra)

    migrate = compose(env, "run", "--rm", "-T", "migrate", check=False, extra_env=extra)
    if migrate.returncode != 0:
        fail(f"migration 失敗（原因見上方訊息）。{MAINTENANCE_HINT if production else ''}")

    compose(env, "up", "-d", "--remove-orphans", extra_env=extra)
    problem = startup_problem(env)
    if problem:
        if production:
            # 沒通過檢查的版本不接流量。
            compose(env, "stop", "nginx", extra_env=extra)
        fail(f"{problem}（make logs 查看原因）。{MAINTENANCE_HINT if production else ''}")

    print(f"已啟動：http://localhost:{env['SYSTEM_PORT']}")
    if lan:
        print("已對區網開放，同一個網路上的人都連得到；用完跑一次 make start 關回只限本機")
