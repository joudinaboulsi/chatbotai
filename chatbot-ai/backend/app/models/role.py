import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import UUIDPKMixin


class Role(Base, UUIDPKMixin):
    """Fixed set of roles: super_admin, admin, support_agent.

    Kept as a table (rather than a bare enum column) so role metadata
    (description) is editable without a migration, per the spec's explicit
    `roles` table requirement.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    users: Mapped[list["User"]] = relationship(back_populates="role")
