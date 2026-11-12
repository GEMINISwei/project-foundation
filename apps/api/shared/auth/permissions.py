"""權限的型別與目錄。

權限值集中定義在 `app/permissions.py` 的 enum (要進 OpenAPI 成為字串聯集, 前端才有編譯期檢查);
每個權限的標籤、分類與相依關係由引入它的模組用 `PermissionSpec` 宣告。目錄把兩者兜起來。

相依關係是「有 A 就一定要有 B」(例如 `users:write` 需要 `users:read`): 儲存角色時自動補上,
所以資料庫裡的權限集合永遠是完整的, 檢查時只需要比對字串。
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Request

from shared.i18n import LangText

#: 超級管理者的權限: 任何檢查都通過。只存在於系統角色, 不能指派給一般角色。
WILDCARD = "*"


class BasePermission(StrEnum):
    """專案的 Permission enum 繼承這個。"""


@dataclass(frozen=True)
class PermissionSpec:
    value: BasePermission
    #: 動作本身 (「查看」) 與所屬分類 (「使用者」): 角色編輯畫面依分類分組。
    label: LangText
    category: LangText
    #: 擁有這個權限就必須同時擁有的權限。
    requires: frozenset[BasePermission] = frozenset()


def has_permission(granted: Iterable[str], required: str) -> bool:
    owned = set(granted)
    return WILDCARD in owned or required in owned


class PermissionCatalog:
    """啟用中模組宣告的所有權限。啟動時驗證宣告與 enum 一致, 之後唯讀。"""

    def __init__(self, enum: type[BasePermission], specs: Iterable[PermissionSpec]) -> None:
        self.specs = tuple(specs)
        self._requires = {
            spec.value.value: {item.value for item in spec.requires} for spec in self.specs
        }
        declared = [spec.value.value for spec in self.specs]
        expected = {member.value for member in enum} - {WILDCARD}
        problems = []
        if len(declared) != len(set(declared)):
            problems.append("有權限被重複宣告")
        if missing := expected - set(declared):
            problems.append(f"enum 有但沒有模組宣告: {sorted(missing)}")
        if extra := set(declared) - expected:
            problems.append(f"模組宣告了 enum 沒有的權限: {sorted(extra)}")
        if unknown := {item for items in self._requires.values() for item in items} - expected:
            problems.append(f"相依到不存在的權限: {sorted(unknown)}")
        if problems:
            raise RuntimeError("權限宣告不一致: " + "; ".join(problems))

    def known(self) -> list[str]:
        return [spec.value.value for spec in self.specs]

    def complete(self, permissions: Iterable[str]) -> list[str]:
        """補上相依的權限 (遞迴), 依宣告順序排列。"""
        result: set[str] = set()
        pending = list(permissions)
        while pending:
            item = pending.pop()
            if item not in result:
                result.add(item)
                pending.extend(self._requires.get(item, ()))
        order = {spec.value.value: index for index, spec in enumerate(self.specs)}
        return sorted(result, key=lambda item: order.get(item, -1))


def get_catalog(request: Request) -> PermissionCatalog:
    """路由用的 dependency: 這個 app 的權限目錄 (隨啟用的模組而定)。"""
    catalog: PermissionCatalog = request.app.state.permission_catalog
    return catalog
