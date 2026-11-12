from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Entity

#: 系統角色的代碼。有代碼的角色由初始資料擁有, 後台不能改也不能停用。
SUPER_ADMIN_CODE = "super_admin"


class Role(Entity):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(unique=True)
    code: Mapped[str | None] = mapped_column(unique=True)
    #: 已補上相依權限的完整集合 (見 PermissionCatalog.complete)。
    permissions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_disabled: Mapped[bool] = mapped_column(default=False)

    @property
    def is_system(self) -> bool:
        return self.code is not None
