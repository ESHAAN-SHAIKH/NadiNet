import uuid
from datetime import datetime, timezone
from sqlalchemy import Float, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy import String
from app.database import Base


class Volunteer(Base):
    __tablename__ = "volunteers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    languages: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    has_transport: Mapped[bool] = mapped_column(Boolean, default=False)
    zone_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.65)
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    availability_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    location_wkt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="volunteer")
    debriefs: Mapped[list["Debrief"]] = relationship("Debrief", back_populates="volunteer")
    kinship_a: Mapped[list["KinshipEdge"]] = relationship("KinshipEdge", foreign_keys="KinshipEdge.volunteer_a_id", back_populates="volunteer_a")
    kinship_b: Mapped[list["KinshipEdge"]] = relationship("KinshipEdge", foreign_keys="KinshipEdge.volunteer_b_id", back_populates="volunteer_b")
