import pytest

from shared.i18n import LangText, Language, current_language, resolve_language


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, Language.ZH),
        ("", Language.ZH),
        ("en-US,en;q=0.9", Language.EN),
        ("fr-FR, en;q=0.5", Language.EN),
        ("zh-TW", Language.ZH),
        ("fr", Language.ZH),
    ],
)
def test_resolve_language_picks_the_first_supported_primary_tag(header, expected):
    assert resolve_language(header) is expected


def test_text_follows_the_request_language_unless_told_otherwise():
    text = LangText(zh="角色", en="Role")
    token = current_language.set(Language.EN)
    try:
        assert text.resolve() == "Role"
        assert text.resolve(Language.ZH) == "角色"
    finally:
        current_language.reset(token)
