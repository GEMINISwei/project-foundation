"""版號只有一個來源 (`app/version.py`), CHANGELOG 要有對應的段落。兩者由 `make release` 一起改。"""

import re
from pathlib import Path

from app.version import APP_VERSION

CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"


def test_version_is_plain_semver():
    assert re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", APP_VERSION)


def test_changelog_has_a_section_for_the_current_version():
    headings = re.findall(r"^## \[(.+?)\]", CHANGELOG.read_text(encoding="utf-8"), flags=re.M)
    assert headings[0] == "Unreleased"
    # 最新的版本段落就是目前的版號: 手動改了其中一邊就會對不上。
    assert headings[1] == APP_VERSION
