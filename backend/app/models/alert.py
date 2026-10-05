import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    """A pollution alert addressed to an authority.

    Lifecycle (human-in-the-loop):
        pending_review  -> created automatically for a HIGH-risk report;
                           NOT sent until a human confirms.
        sent            -> operator confirmed; message dispatched (or dry-run
                           logged if ALERTS_DRY_RUN).
        dismissed       -> operator judged it a false alarm.

    The alert is never auto-dispatched: creation and sending are separate steps.
    """

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    water_body_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("water_bodies.id", ondelete="CASCADE"), nullable=False
    )
    authority_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("authorities.id", ondelete="SET NULL"), nullable=True
    )

    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    satellite_corroboration: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    channel: Mapped[str] = mapped_column(String(20), default="email")
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    send_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # dry-run / error / sent detail

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Alert(status='{self.status}', risk='{self.risk_level}', wb='{self.water_body_id}')>"
