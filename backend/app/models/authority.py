import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Authority(Base):
    """A municipal / pollution-control authority that can receive alerts.

    Contacts are configured by the operator. The seed ships clearly-labelled
    EXAMPLE/demo contacts (example.gov addresses) that must be replaced with
    real, authorized recipients before any live sending.
    """

    __tablename__ = "authorities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # May be empty when only a complaint portal is known; a human must set a
    # verified address before live sending.
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Official website / complaint portal (verifiable, safe to display).
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # True only when a human has confirmed the email against the official source.
    verified: Mapped[bool] = mapped_column(default=False)
    # Jurisdiction used for matching: a city/region string, matched against the
    # water body's city/state. Null = fallback/default authority.
    jurisdiction: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Authority(name='{self.name}', jurisdiction='{self.jurisdiction}')>"
