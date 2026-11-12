import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.permissions import Permission
from shared import context
from shared.auth.identity import Identity, require
from shared.auth.permissions import PermissionCatalog, get_catalog
from shared.db.pagination import Page, PageParams
from shared.rate_limit import RateLimiter

from . import account, service
from .schema import (
    LoginRequest,
    Me,
    PasswordChange,
    PasswordReset,
    ProfileUpdate,
    Token,
    UserCreate,
    UserInfo,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])

Current = Annotated[Identity, Depends(require())]
Reader = Annotated[Identity, Depends(require(Permission.USERS_READ))]
Writer = Annotated[Identity, Depends(require(Permission.USERS_WRITE))]

# IP + 帳號: 只用 IP 會讓同一間辦公室互相影響, 只用帳號可以被拿來鎖定別人。
login_limiter = RateLimiter("login", max_attempts=10, window_seconds=300)
# 只看 IP, 上限訂寬: 擋「同一個來源對整份帳號清單各試幾次」。登入成功也不歸零,
# 否則攻擊者用自己的帳號登入一次就把額度洗回來。
login_ip_limiter = RateLimiter("login_ip", max_attempts=50, window_seconds=300)
# 擋密碼雜湊的 CPU 消耗, 也讓偷到登入狀態的人不能慢慢試舊密碼。
password_change_limiter = RateLimiter("password_change", max_attempts=10, window_seconds=300)


@router.post("/login")
async def login(data: LoginRequest) -> Token:
    ip = context.client_ip.get()
    await login_ip_limiter.check(ip)
    key = f"{ip}:{data.username}"
    await login_limiter.check(key)
    token = await account.login(data)
    await login_limiter.reset(key)
    return token


@router.get("/me")
async def get_me(
    identity: Current, catalog: Annotated[PermissionCatalog, Depends(get_catalog)]
) -> Me:
    return account.me(identity, catalog)


@router.patch("/me", status_code=204)
async def update_my_profile(data: ProfileUpdate, identity: Current) -> None:
    await account.update_profile(identity, data)


@router.put("/me/password")
async def change_my_password(data: PasswordChange, identity: Current) -> Token:
    """換自己的密碼。所有既有的登入都會失效, 呼叫端要改用回傳的新憑證。"""
    key = str(identity.id)
    await password_change_limiter.check(key)
    token = await account.change_password(identity, data)
    await password_change_limiter.reset(key)
    return token


@router.post("/me/logout", status_code=204)
async def logout(identity: Current) -> None:
    """登出。這個帳號在所有裝置上的登入都會失效。"""
    await account.logout(identity)


@router.get("")
async def list_users(
    _: Reader,
    params: Annotated[PageParams, Query()],
    keyword: str | None = None,
    role_id: uuid.UUID | None = None,
    unassigned: bool = False,
    is_disabled: bool | None = None,
) -> Page[UserInfo]:
    """`keyword` 比對帳號與暱稱; `unassigned` 只列出沒有任何角色的帳號。"""
    return await service.list_users(
        params, keyword=keyword, role_id=role_id, unassigned=unassigned, is_disabled=is_disabled
    )


@router.post("", status_code=201)
async def create_user(data: UserCreate, actor: Writer) -> UserInfo:
    return await service.create_user(data, actor=actor)


@router.get("/{user_id}")
async def get_user(user_id: uuid.UUID, _: Reader) -> UserInfo:
    return await service.get_user(user_id)


@router.put("/{user_id}")
async def update_user(user_id: uuid.UUID, data: UserUpdate, actor: Writer) -> UserInfo:
    return await service.update_user(user_id, data, actor=actor)


@router.put("/{user_id}/password", status_code=204)
async def reset_user_password(user_id: uuid.UUID, data: PasswordReset, actor: Writer) -> None:
    """替別人重設密碼。對方所有既有的登入都會失效。"""
    await service.reset_password(user_id, data, actor=actor)


@router.post("/{user_id}/disable")
async def disable_user(user_id: uuid.UUID, actor: Writer) -> UserInfo:
    """停用帳號。對方所有既有的登入都會失效; 帳號被別的資料參照著, 所以沒有真的刪除。"""
    return await service.disable_user(user_id, actor=actor)
