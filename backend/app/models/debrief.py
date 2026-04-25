import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Debrief(Base):
    __tablename__ = "debriefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    volunteer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)
    need_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("needs.id"), nullable=False)
    resolution: Mapped[str] = mapped_column(Text, nullable=False)  # resolved|partial|unresolved
    people_helped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task: Mapped["Task"] = relationship("Task", back_populates="debrief")
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="debriefs")
    need: Mapped["Need"] = relationship("Need", back_populates="debriefs")
