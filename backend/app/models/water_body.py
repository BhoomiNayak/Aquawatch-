import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.database import Base


class WaterBody(Base):
    __tablename__ = "water_bodies"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location = mapped_column(
        Geometry("POINT", srid=4326),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(50), default="lake")
    city: Mapped[str] = mapped_column(String(100), default="Bengaluru")
    state: Mapped[str] = mapped_column(String(100), default="Karnataka")

    # Denormalized risk fields (updated on each new report)
    current_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    current_risk_level: Mapped[str] = mapped_column(String(20), default="low")
    total_reports: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    last_report_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    reports = relationship("Report", back_populates="water_body", lazy="dynamic")
    risk_scores = relationship("RiskScore", back_populates="water_body", lazy="dynamic")

    def __repr__(self):
        return f"<WaterBody(name='{self.name}', risk='{self.current_risk_level}')>"
