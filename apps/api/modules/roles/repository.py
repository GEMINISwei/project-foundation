"""roles 資料表的查詢。回傳 ORM 物件, 不做業務判斷。"""

import uuid
from collections.abc import Iterable

from sqlalchemy import ColumnElement, select

from shared.db.pagination import PageParams, PageResult, paginate
from shared.db.session import db

from .model import Role


async def get(role_id: uuid.UUID) -> Role | None:
    return await db().get(Role, role_id)


async def get_by_code(code: str) -> Role | None:
    return await db().scalar(select(Role).where(Role.code == code))


async def get_many(role_ids: Iterable[uuid.UUID]) -> list[Role]:
    ids = set(role_ids)
    if not ids:
        return []
    return list(
        (await db().scalars(select(Role).where(Role.id.in_(ids)).order_by(Role.name))).all()
    )


async def name_taken(name: str, *, except_id: uuid.UUID | None = None) -> bool:
    statement = select(Role.id).where(Role.name == name)
    if except_id is not None:
        statement = statement.where(Role.id != except_id)
    return await db().scalar(statement) is not None


def _filters(name: str | None, is_disabled: bool | None) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if name:
        conditions.append(Role.name.icontains(name, autoescape=True))
    if is_disabled is not None:
        conditions.append(Role.is_disabled == is_disabled)
    return conditions


async def page(
    params: PageParams, *, name: str | None, is_disabled: bool | None
) -> PageResult[Role]:
    return await paginate(Role, params, where=_filters(name, is_disabled))


async def list_all(*, is_disabled: bool | None) -> list[Role]:
    statement = select(Role).where(*_filters(None, is_disabled)).order_by(Role.created_at, Role.id)
    return list((await db().scalars(statement)).all())


async def add(role: Role) -> Role:
    db().add(role)
    await db().flush()
    return role
