import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from shared.auth.tokens import create_token, parse_token
from shared.errors import AppError
from shared.settings import settings


def encode(**overrides):
    payload = {
        "sub": str(uuid.uuid7()),
        "ver": 1,
        "aud": settings.project_name,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **overrides,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def code_of(token: str | None) -> str:
    with pytest.raises(AppError) as raised:
        parse_token(token)
    return raised.value.spec.code


def test_round_trip_keeps_user_and_version():
    user_id = uuid.uuid7()
    claims = parse_token(create_token(user_id, 7))
    assert (claims.user_id, claims.auth_version) == (user_id, 7)


def test_missing_token_is_reported_separately_from_invalid_ones():
    assert code_of(None) == "auth.token_missing"
    assert code_of("") == "auth.token_missing"
    assert code_of("not-a-token") == "auth.token_invalid"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"aud": "another-system"},
        {"ver": "1"},
        {"ver": None},
        {"sub": "not-a-uuid"},
    ],
)
def test_rejects_expired_foreign_or_malformed_tokens(overrides):
    assert code_of(encode(**overrides)) == "auth.token_invalid"


def test_rejects_tokens_signed_with_another_key_or_without_signature():
    payload = {"sub": str(uuid.uuid7()), "ver": 1, "aud": settings.project_name}
    payload["exp"] = datetime.now(UTC) + timedelta(hours=1)
    assert code_of(jwt.encode(payload, "x" * 32, algorithm="HS256")) == "auth.token_invalid"
    assert code_of(jwt.encode(payload, "", algorithm="none")) == "auth.token_invalid"
