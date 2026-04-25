import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reporters.id"), nullable=True)
    source_channel: Mapped[str] = mapped_column(Text, nullable=False)  # whatsapp|ocr|app|csv|debrief
    zone_id: Mapped[str] = mapped_column(Text, nullable=False)
    need_category: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_est: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="watch")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    corroboration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("needs.id"), nullable=True)
    manually_confirmed: Mapped[bool] = mapped_column(default=False)

    reporter: Mapped["Reporter"] = relationship("Reporter", back_populates="signals")
    need: Mapped["Need | None"] = relationship("Need", back_populates="signals")
