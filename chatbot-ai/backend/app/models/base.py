import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Build a Postgres ENUM column type whose type name and stored labels
    exactly match what the Alembic migrations create (lowercase `.value`
    strings, not the Python member names) — SQLAlchemy's bare `Mapped[SomeEnum]`
    default instead derives the type name from the class name and stores
    member *names*, which silently mismatches a hand-written migration."""

    return SAEnum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    # eager_defaults: an `onupdate=func.clock_timestamp()` column is otherwise left
    # "expired" after an UPDATE (SQLAlchemy doesn't know the server-computed
    # value), so the next attribute access issues a lazy SELECT — which
    # breaks under async since that reload isn't wrapped in greenlet_spawn.
    # RETURNING fetches it inline during the flush instead.
    __mapper_args__ = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), onupdate=func.clock_timestamp(), nullable=False
    )
