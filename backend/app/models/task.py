import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    need_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("needs.id"), nullable=False)
    volunteer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kinship_bonus: Mapped[bool] = mapped_column(Boolean, default=False)

    need: Mapped["Need"] = relationship("Need", back_populates="tasks")
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="tasks")
    debrief: Mapped["Debrief | None"] = relationship("Debrief", back_populates="task")
