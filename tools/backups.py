"""備份檔的命名與清單。

一次備份是一組共用檔名的檔案, 只差副檔名:

    backups/<專案>_v<版號>_<日期>_<時間>.dump         資料庫 (pg_dump -Fc)
    backups/<專案>_v<版號>_<日期>_<時間>.tar          上傳的檔案
    backups/<專案>_v<版號>_<日期>_<時間>.logs.tar.gz  當下各容器的 log (只給人看)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tools.env import REPO_ROOT

BACKUP_DIR = REPO_ROOT / "backups"
KINDS = ("dump", "tar", "logs.tar.gz")
_PATTERN = re.compile(
    r"^(?P<stem>.+_v(?P<version>\d+\.\d+\.\d+)_(?P<day>\d{8})_(?P<time>\d{6}))\.(?P<kind>dump|tar|logs\.tar\.gz)$"
)


@dataclass(frozen=True)
class Backup:
    path: Path
    stem: str
    version: str
    stamp: str  # 日期加時間, 可以直接排序
    kind: str

    @property
    def label(self) -> str:
        s = self.stamp
        return f"v{self.version} {s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}"


def parse(path: Path) -> Backup | None:
    match = _PATTERN.match(path.name)
    if match is None:
        return None
    return Backup(
        path=path,
        stem=match["stem"],
        version=match["version"],
        stamp=match["day"] + match["time"],
        kind=match["kind"],
    )


def list_backups(kind: str, version: str | None = None) -> list[Backup]:
    """某一種備份檔, 新到舊; 給了 `version` 就只列那一版的。檔名不合格式的不列。"""
    found = [backup for path in BACKUP_DIR.glob("*") if (backup := parse(path))]
    return sorted(
        (b for b in found if b.kind == kind and (version is None or b.version == version)),
        key=lambda b: b.stamp,
        reverse=True,
    )


def to_prune(keep: int) -> list[Path]:
    """保留最近 `keep` 組之後要刪除的檔案。以組為單位、依檔名的時間、不分版號。"""
    found = [backup for path in BACKUP_DIR.glob("*") if (backup := parse(path))]
    stems = sorted({(b.stamp, b.stem) for b in found}, reverse=True)
    dropped = {stem for _, stem in stems[keep:]}
    return sorted(b.path for b in found if b.stem in dropped)
