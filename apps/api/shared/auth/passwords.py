"""密碼雜湊 (bcrypt)。

bcrypt 一次約 100–300ms 的純 CPU 工作, 直接在 async 函式裡呼叫會停住所有請求, 所以丟到執行緒
(bcrypt 會釋放 GIL)。
"""

import asyncio

import bcrypt

#: bcrypt 只看前 72 bytes, 超過的部分會被安靜地忽略, 所以在輸入時就擋下。
MAX_PASSWORD_BYTES = 72
#: 雜湊的成本。測試會調低, 其他地方不要動。
ROUNDS = 12


def hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(ROUNDS)).decode()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password_sync, password)


_DUMMY_HASH = hash_password_sync("dummy-password")


async def verify_password(password: str, password_hash: str | None) -> bool:
    """比對密碼。帳號不存在 (`password_hash` 是 None) 時也比對一次假的雜湊:
    否則回應時間本身就洩漏了帳號存不存在。"""
    matched = await asyncio.to_thread(
        bcrypt.checkpw, password.encode(), (password_hash or _DUMMY_HASH).encode()
    )
    return matched and password_hash is not None
