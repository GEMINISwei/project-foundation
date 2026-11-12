"""登入憑證 (JWT, HS256)。

憑證帶使用者的 `auth_version`: 每個請求都跟資料庫比對, 對不上就要重新登入。撤銷就是把版本 +1
(改密碼、登出、停用), 不需要 refresh token 或黑名單。到期時間是硬上限, 不續期。
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from shared.errors import ErrorSpec
from shared.i18n import LangText
from shared.settings import settings

# 演算法寫死: 接受設定值的話, 設成 none 會讓未簽名的憑證通過驗證。
_ALGORITHM = "HS256"

TOKEN_MISSING = ErrorSpec(
    401, "auth.token_missing", LangText(zh="尚未登入，請重新登入", en="Not signed in")
)
TOKEN_INVALID = ErrorSpec(
    401, "auth.token_invalid", LangText(zh="登入資訊無效，請重新登入", en="Invalid session")
)
TOKEN_REVOKED = ErrorSpec(
    401, "auth.token_revoked", LangText(zh="登入已失效，請重新登入", en="Session expired")
)


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    auth_version: int


def create_token(user_id: uuid.UUID, auth_version: int) -> str:
    payload = {
        "sub": str(user_id),
        "ver": auth_version,
        # 同一把金鑰簽給別套系統的憑證不能拿來這裡用。
        "aud": settings.project_name,
        "exp": datetime.now(UTC) + timedelta(hours=settings.expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def parse_token(token: str | None) -> TokenClaims:
    if not token:
        raise TOKEN_MISSING()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_ALGORITHM],
            audience=settings.project_name,
            options={"require": ["sub", "ver", "aud", "exp"]},
        )
        version = payload["ver"]
        if type(version) is not int:
            raise ValueError("ver")
        return TokenClaims(user_id=uuid.UUID(payload["sub"]), auth_version=version)
    except (jwt.PyJWTError, ValueError, TypeError) as error:
        raise TOKEN_INVALID() from error
