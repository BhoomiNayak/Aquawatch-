import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    water_body_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("water_bodies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Score
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # Component averages (for the scoring window)
    avg_algae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_foam_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_turbidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Time window
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    water_body = relationship("WaterBody", back_populates="risk_scores")

    def __repr__(self):
        return f"<RiskScore(water_body='{self.water_body_id}', score={self.risk_score}, level='{self.risk_level}')>"
