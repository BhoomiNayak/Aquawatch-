"""
Seed example authorities for the alerting feature.

IMPORTANT: these are PLACEHOLDER / DEMO contacts using the reserved example.org
domain. They are NOT real municipal addresses. Replace them with real,
authorized recipients before enabling live sending (ALERTS_DRY_RUN=false).

Usage:
    cd backend
    python seed_authorities.py
"""

import uuid

from app.database import SessionLocal, engine, Base
from app.models import authority, alert, water_body, report, risk_score  # noqa: F401
from app.models.authority import Authority

# (name, email, jurisdiction, is_default) — jurisdiction matches WaterBody.city/state
EXAMPLE_AUTHORITIES = [
    ("Karnataka State Pollution Control Board (DEMO)", "kspcb-demo@example.org", "Karnataka", False),
    ("BBMP Lakes Division (DEMO)",                      "bbmp-lakes-demo@example.org", "Bengaluru", False),
    ("Telangana Pollution Control Board (DEMO)",        "tspcb-demo@example.org", "Telangana", False),
    ("Delhi Pollution Control Committee (DEMO)",        "dpcc-demo@example.org", "Delhi", False),
    ("National Water Authority (DEMO fallback)",        "water-authority-demo@example.org", None, True),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {a.email for a in db.query(Authority).all()}
        added = 0
        for name, email, jurisdiction, is_default in EXAMPLE_AUTHORITIES:
            if email in existing:
                continue
            db.add(Authority(
                id=str(uuid.uuid4()), name=name, email=email,
                jurisdiction=jurisdiction, is_default=is_default,
            ))
            added += 1
        db.commit()
        total = db.query(Authority).count()
        print(f"Seeded {added} authorities ({total} total).")
        print("NOTE: all contacts are example.org DEMO placeholders — replace "
              "with real authorized recipients before live sending.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
