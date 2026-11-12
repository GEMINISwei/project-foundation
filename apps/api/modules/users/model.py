import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base, Entity


class UserRole(Base):
    """使用者擁有的角色。角色屬於 roles 模組, 這裡只以 id 參照 (外鍵用字串宣告)。"""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # RESTRICT: 還有人擁有的角色不能被刪除, 資料庫會擋下並由平台轉成 409。
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class User(Entity):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True)
    nickname: Mapped[str]
    password_hash: Mapped[str]
    is_disabled: Mapped[bool] = mapped_column(default=False)
    #: 簽進登入憑證的版本; +1 就讓這個帳號所有裝置的登入失效。
    auth_version: Mapped[int] = mapped_column(default=1)

    role_links: Mapped[list[UserRole]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    @property
    def role_ids(self) -> list[uuid.UUID]:
        return [link.role_id for link in self.role_links]
