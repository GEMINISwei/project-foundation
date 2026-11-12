"""雙語文字。`Language` 是前後端語系清單的唯一來源, 會進 OpenAPI。"""

from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum


class Language(StrEnum):
    """系統支援的語系。"""

    ZH = "zh"
    EN = "en"


DEFAULT_LANGUAGE = Language.ZH

#: 這次請求的語系, 由平台的 middleware 依 Accept-Language 設定。
current_language: ContextVar[Language] = ContextVar("current_language", default=DEFAULT_LANGUAGE)


@dataclass(frozen=True)
class LangText:
    zh: str
    en: str

    def resolve(self, language: Language | None = None) -> str:
        """依語系取出字串; 沒指定時用這次請求的語系。

        只在收件人就是這次請求的發起者時才能省略參數: 背景任務與廣播要自己指定語系。
        """
        return self.en if (language or current_language.get()) is Language.EN else self.zh


def resolve_language(accept_language: str | None) -> Language:
    """從 Accept-Language 挑出支援的語系。只比對主要語言 (`en-US` → `en`), 不處理 q 權重;
    前端的 resolveLocale() 是同一個行為。"""
    for part in (accept_language or "").split(","):
        primary = part.split(";")[0].strip().lower().split("-")[0]
        if primary in Language:
            return Language(primary)
    return DEFAULT_LANGUAGE
