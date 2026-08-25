import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

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

    # Location (where photo was taken)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location = mapped_column(
        Geometry("POINT", srid=4326),
        nullable=False,
    )

    # User input
    contamination_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reporter_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # CV Analysis Results
    forel_ule_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forel_ule_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    algae_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    foam_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    foam_coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    turbidity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Composite score
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    water_body = relationship("WaterBody", back_populates="reports")

    def __repr__(self):
        return f"<Report(water_body='{self.water_body_id}', risk='{self.risk_level}', score={self.composite_score})>"
