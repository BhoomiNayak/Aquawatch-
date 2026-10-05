"""
Seed real Indian pollution-control authorities for the alerting feature.

HONESTY / SAFETY NOTES
----------------------
- The NAMES, JURISDICTIONS, and WEBSITE / complaint-portal URLs below are the
  real, publicly listed official boards.
- EMAILS are intentionally sparse: an address is filled ONLY where it appears
  on an official .gov.in / .nic.in page, and even then `verified=False` until a
  human confirms it against the official source. Boards whose official email we
  could not confirm are left with email="" — the operator must add a verified
  address (or use the board's complaint portal) before any send.
- Government emails change and a wrong address could misfire; therefore alerts
  stay DRY-RUN by default and never auto-send. Confirm emails on each board's
  website, set `verified=True`, and only then disable dry-run.

Usage:
    cd backend
    python seed_authorities.py
"""

import uuid

from app.database import SessionLocal, engine, Base
from app.models import authority, alert, water_body, report, risk_score  # noqa: F401
from app.models.authority import Authority

# (name, email, website, jurisdiction, is_default)
#   email == "" means: not confirmed; operator must set a verified address.
#   jurisdiction matches WaterBody.city or WaterBody.state (case-insensitive).
AUTHORITIES = [
    # National board — default fallback
    ("Central Pollution Control Board (CPCB)",
     "ccb.cpcb@nic.in", "https://cpcb.nic.in/contact-us/", None, True),

    # State / city boards (confirm email on the website before enabling send)
    ("Karnataka State Pollution Control Board (KSPCB)",
     "", "https://kspcb.karnataka.gov.in/", "Karnataka", False),
    ("KSPCB — Bengaluru",
     "", "https://kspcb.karnataka.gov.in/", "Bengaluru", False),
    ("Telangana State Pollution Control Board (TGPCB/TSPCB)",
     "", "https://tspcb.cgg.gov.in/", "Telangana", False),
    ("TSPCB — Hyderabad",
     "", "https://tspcb.cgg.gov.in/", "Hyderabad", False),
    ("Delhi Pollution Control Committee (DPCC)",
     "msdpcc@nic.in", "https://dpcc.delhi.gov.in/", "Delhi", False),
    ("Tamil Nadu Pollution Control Board (TNPCB)",
     "", "https://tnpcb.gov.in/", "Tamil Nadu", False),
    ("TNPCB — Chennai",
     "", "https://tnpcb.gov.in/", "Chennai", False),
    ("Maharashtra Pollution Control Board (MPCB)",
     "", "https://mpcb.gov.in/", "Maharashtra", False),
    ("West Bengal Pollution Control Board (WBPCB)",
     "", "https://www.wbpcb.gov.in/", "West Bengal", False),
    ("Uttar Pradesh Pollution Control Board (UPPCB)",
     "", "https://www.uppcb.com/", "Uttar Pradesh", False),
    ("Gujarat Pollution Control Board (GPCB)",
     "", "https://gpcb.gujarat.gov.in/", "Gujarat", False),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {a.name for a in db.query(Authority).all()}
        added = 0
        for name, email, website, jurisdiction, is_default in AUTHORITIES:
            if name in existing:
                continue
            db.add(Authority(
                id=str(uuid.uuid4()), name=name, email=email, website=website,
                verified=False, jurisdiction=jurisdiction, is_default=is_default,
            ))
            added += 1
        db.commit()
        total = db.query(Authority).count()
        with_email = db.query(Authority).filter(Authority.email != "").count()
        print(f"Seeded {added} authorities ({total} total; {with_email} with a "
              f"provisional email, 0 verified).")
        print("ACTION REQUIRED before live sending:")
        print("  1. Confirm each board's email on its official website (set verified=True).")
        print("  2. Keep ALERTS_DRY_RUN=true until confirmed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
