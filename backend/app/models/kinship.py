import uuid
from datetime import datetime, timezone
from sqlalchemy import Float, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class KinshipEdge(Base):
    __tablename__ = "kinship_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    volunteer_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)
    volunteer_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)
    co_deployments: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_deployed: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("volunteer_a_id", "volunteer_b_id", name="uq_kinship_pair"),)

    volunteer_a: Mapped["Volunteer"] = relationship("Volunteer", foreign_keys=[volunteer_a_id], back_populates="kinship_a")
    volunteer_b: Mapped["Volunteer"] = relationship("Volunteer", foreign_keys=[volunteer_b_id], back_populates="kinship_b")
