import uuid
from datetime import datetime, timezone
from sqlalchemy import Float, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Need(Base):
    __tablename__ = "needs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[str] = mapped_column(Text, nullable=False)
    need_category: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    u_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    g_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    v_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    c_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lambda_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    population_est: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    first_reported: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_corroborated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # PostGIS location (stored as text WKT; we use raw SQL for actual geo operations)
    location_wkt: Mapped[str | None] = mapped_column(Text, nullable=True)

    signals: Mapped[list["Signal"]] = relationship("Signal", back_populates="need")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="need")
    debriefs: Mapped[list["Debrief"]] = relationship("Debrief", back_populates="need")
