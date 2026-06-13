import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    """Root base for all models."""
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKey:
    """Adds a UUID primary key to any model."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class SchoolScopedMixin:
    """
    Every table (except GhanaRegion, GhanaDistrict, GhanaPublicHoliday,
    StaffPosition templates, SubjectCatalogue GES entries, GradingScale defaults)
    carries school_id for Row Level Security.

    Models that are school-scoped inherit this mixin.
    Models that are system-wide (seeded reference tables) do not.
    """
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
