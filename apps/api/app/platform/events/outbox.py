"""
Transactional Outbox Pattern Implementation.
Guarantees reliable at-least-once asynchronous event delivery.
"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEvent(Base):
    """
    Append-only outbox event recorded in the same database transaction
    as the business state changes.
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")

    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus), default=OutboxStatus.PENDING, nullable=False, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __init__(self, **kw: Any) -> None:
        if "status" not in kw:
            kw["status"] = OutboxStatus.PENDING
        if "schema_version" not in kw:
            kw["schema_version"] = "1.0.0"
        if "retry_count" not in kw:
            kw["retry_count"] = 0
        super().__init__(**kw)

    __table_args__ = (
        Index("ix_outbox_events_tenant_status", "tenant_id", "status"),
        Index("ix_outbox_events_created_status", "created_at", "status"),
    )
