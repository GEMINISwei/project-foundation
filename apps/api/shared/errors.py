"""錯誤的定義與回應格式。

每個錯誤有固定的代碼 (`roles.name_exists`): 訊息會隨語系變, 代碼不會, 前端分支與 log 搜尋都用它。
回應一律是 `ErrorBody`, 帶 request id, 使用者回報時可以直接 `make logs trace <id>`。

模組在自己的 `errors.py` 宣告, 用的時候 `raise ROLE_NOT_FOUND()`:

    ROLE_NOT_FOUND = ErrorSpec(
        404, "roles.not_found", LangText(zh="角色不存在", en="Role not found")
    )
"""

from dataclasses import dataclass

from pydantic import BaseModel

from shared.i18n import LangText


class FieldError(BaseModel):
    """單一欄位的錯誤。"""

    field: str
    message: str


class ErrorBody(BaseModel):
    """所有錯誤回應共用的格式。"""

    code: str
    message: str
    request_id: str
    fields: list[FieldError] = []


class AppError(Exception):
    def __init__(
        self,
        spec: ErrorSpec,
        *,
        headers: dict[str, str] | None = None,
        fields: list[FieldError] | None = None,
    ) -> None:
        super().__init__(spec.code)
        self.spec = spec
        self.headers = headers
        self.fields = fields or []


@dataclass(frozen=True)
class ErrorSpec:
    status: int
    code: str
    text: LangText

    def __call__(
        self,
        *,
        headers: dict[str, str] | None = None,
        fields: list[FieldError] | None = None,
    ) -> AppError:
        return AppError(self, headers=headers, fields=fields)


def found[T](value: T | None, error: ErrorSpec) -> T:
    """查不到就丟指定的錯誤, 查到了回傳去掉 None 的型別。"""
    if value is None:
        raise error()
    return value


# ── 平台層的錯誤 ─────────────────────────────────────────────────────────────

INTERNAL = ErrorSpec(500, "internal", LangText(zh="伺服器發生錯誤", en="Internal server error"))
VALIDATION = ErrorSpec(
    422, "validation.invalid", LangText(zh="輸入的資料不正確", en="Invalid input")
)
INVALID_CURSOR = ErrorSpec(
    400, "pagination.invalid_cursor", LangText(zh="分頁游標無效", en="Invalid pagination cursor")
)
STILL_REFERENCED = ErrorSpec(
    409,
    "data.still_referenced",
    LangText(zh="仍有其他資料使用中，無法刪除", en="Still referenced by other data"),
)
REFERENCE_NOT_FOUND = ErrorSpec(
    409,
    "data.reference_not_found",
    LangText(zh="參照的資料不存在", en="Referenced data does not exist"),
)

# 422 的欄位訊息: pydantic 的錯誤型別 → 雙語文字, 沒列到的用 FIELD_INVALID。
FIELD_INVALID = LangText(zh="格式不正確", en="Invalid value")
FIELD_MESSAGES: dict[str, LangText] = {
    "missing": LangText(zh="必填", en="Required"),
    "string_too_short": LangText(zh="長度不足", en="Too short"),
    "string_too_long": LangText(zh="長度超過上限", en="Too long"),
    "uuid_parsing": LangText(zh="無效的資料 ID", en="Invalid ID"),
    "enum": LangText(zh="不是允許的選項", en="Not an allowed option"),
    "greater_than_equal": LangText(zh="數值太小", en="Value too small"),
    "less_than_equal": LangText(zh="數值太大", en="Value too large"),
}
