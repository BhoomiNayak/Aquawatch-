"""
Seed Script — Populates the database with demo data.

Inserts:
- 10 Bengaluru water bodies with GPS coordinates
- 3-5 fake reports per water body (varied scores)
- 4 weeks of historical risk scores for trend charts

Usage:
    cd backend
    python seed.py
"""

import uuid
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from app.database import engine, SessionLocal, Base
from app.models.water_body import WaterBody
from app.models.report import Report
from app.models.risk_score import RiskScore


# 10 Bengaluru water bodies with realistic risk profiles
WATER_BODIES = [
    {
        "name": "Ulsoor Lake",
        "lat": 12.9825, "lng": 77.6200,
        "type": "lake",
        "risk_profile": "moderate",  # central, mixed quality
    },
    {
        "name": "Sankey Tank",
        "lat": 13.0080, "lng": 77.5730,
        "type": "tank",
        "risk_profile": "low",  # well-maintained
    },
    {
        "name": "Bellandur Lake",
        "lat": 12.9373, "lng": 77.6784,
        "type": "lake",
        "risk_profile": "high",  # famously polluted
    },
    {
        "name": "Yediyur Lake",
        "lat": 12.9380, "lng": 77.5700,
        "type": "lake",
        "risk_profile": "low",  # small, clean
    },
    {
        "name": "Puttenahalli Lake",
        "lat": 12.8900, "lng": 77.5880,
        "type": "lake",
        "risk_profile": "low",  # community managed
    },
    {
        "name": "Agara Lake",
        "lat": 12.9250, "lng": 77.6380,
        "type": "lake",
        "risk_profile": "moderate",  # some algae
    },
    {
        "name": "Lalbagh Lake",
        "lat": 12.9507, "lng": 77.5848,
        "type": "lake",
        "risk_profile": "low",  # protected area
    },
    {
        "name": "Kaikondrahalli Lake",
        "lat": 12.9100, "lng": 77.6740,
        "type": "lake",
        "risk_profile": "low",  # restored wetland
    },
    {
        "name": "Jakkur Lake",
        "lat": 13.0700, "lng": 77.6100,
        "type": "lake",
        "risk_profile": "moderate",  # treated sewage inlet
    },
    {
        "name": "Hennur Lake",
        "lat": 13.0450, "lng": 77.6350,
        "type": "lake",
        "risk_profile": "moderate",  # urban runoff
    },
]

# Score ranges for each risk profile
RISK_PROFILES = {
    "low": {"score_range": (5, 14), "contamination_types": ["others", "algal_bloom"]},
    "moderate": {"score_range": (16, 30), "contamination_types": ["sewage", "algal_bloom", "agricultural_runoff", "others"]},
    "high": {"score_range": (36, 55), "contamination_types": ["industrial_discharge", "sewage", "foam", "solid_waste"]},
}


def generate_report_data(risk_profile: str) -> dict:
    """Generate realistic fake report data for a given risk profile."""
    profile = RISK_PROFILES[risk_profile]
    score = random.uniform(*profile["score_range"])
    contamination = random.choice(profile["contamination_types"])

    # Generate CV values that match the score roughly
    if risk_profile == "low":
        algae = random.uniform(0, 8)
        foam_cov = random.uniform(0, 2)
        foam_detected = foam_cov > 1
        turbidity = random.uniform(60, 95)
        fu_index = random.randint(1, 6)
    elif risk_profile == "moderate":
        algae = random.uniform(5, 35)
        foam_cov = random.uniform(0, 10)
        foam_detected = foam_cov > 3
        turbidity = random.uniform(30, 65)
        fu_index = random.randint(7, 14)
    else:  # high
        algae = random.uniform(20, 70)
        foam_cov = random.uniform(5, 40)
        foam_detected = True
        turbidity = random.uniform(5, 35)
        fu_index = random.randint(14, 21)

    from app.utils.forel_ule import get_fu_color_name
    fu_color = get_fu_color_name(fu_index)

    # Risk level from score
    if score <= 15:
        risk_level = "low"
    elif score <= 35:
        risk_level = "moderate"
    else:
        risk_level = "high"

    names = ["Rahul S", "Priya M", "Arjun K", "Sneha R", "Vikram P", "Anita D", None, None]

    return {
        "contamination_type": contamination,
        "reporter_name": random.choice(names),
        "notes": None,
        "forel_ule_index": fu_index,
        "forel_ule_color": fu_color,
        "algae_percentage": round(algae, 1),
        "foam_detected": foam_detected,
        "foam_coverage_pct": round(foam_cov, 1),
        "turbidity_score": round(turbidity, 1),
        "composite_score": round(score, 1),
        "risk_level": risk_level,
    }


def seed_database():
    """Main seed function."""
    print("AquaWatch — Database Seeder")
    print("=" * 50)

    # Create tables
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    # Enable PostGIS extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

    db = SessionLocal()

    try:
        # Check if already seeded
        existing = db.query(WaterBody).count()
        if existing > 0:
            print(f"Database already has {existing} water bodies. Skipping seed.")
            print("To re-seed, drop and recreate the database.")
            return

        now = datetime.now(timezone.utc)

        # Insert water bodies
        print(f"\nInserting {len(WATER_BODIES)} water bodies...")
        water_body_records = []

        for wb_data in WATER_BODIES:
            wb_id = str(uuid.uuid4())
            profile = wb_data["risk_profile"]
            score_range = RISK_PROFILES[profile]["score_range"]
            current_score = random.uniform(*score_range)

            if current_score <= 15:
                current_level = "low"
            elif current_score <= 35:
                current_level = "moderate"
            else:
                current_level = "high"

            point_wkt = f"SRID=4326;POINT({wb_data['lng']} {wb_data['lat']})"

            wb = WaterBody(
                id=wb_id,
                name=wb_data["name"],
                latitude=wb_data["lat"],
                longitude=wb_data["lng"],
                location=point_wkt,
                type=wb_data["type"],
                city="Bengaluru",
                state="Karnataka",
                current_risk_score=round(current_score, 1),
                current_risk_level=current_level,
                total_reports=0,
                created_at=now - timedelta(days=30),
                updated_at=now,
            )
            db.add(wb)
            water_body_records.append((wb, wb_data["risk_profile"]))
            print(f"  ✓ {wb_data['name']} ({current_level}, score={current_score:.1f})")

        db.flush()

        # Insert reports for each water body (3-5 per body)
        print(f"\nInserting reports...")
        total_reports = 0

        for wb, risk_profile in water_body_records:
            num_reports = random.randint(3, 6)

            for i in range(num_reports):
                report_data = generate_report_data(risk_profile)
                # Scatter report timestamps over last 2 weeks
                report_time = now - timedelta(
                    days=random.uniform(0, 14),
                    hours=random.uniform(0, 23),
                )

                # Slight GPS offset from water body center
                lat_offset = random.uniform(-0.002, 0.002)
                lng_offset = random.uniform(-0.002, 0.002)
                rep_lat = wb.latitude + lat_offset
                rep_lng = wb.longitude + lng_offset
                point_wkt = f"SRID=4326;POINT({rep_lng} {rep_lat})"

                report = Report(
                    id=str(uuid.uuid4()),
                    water_body_id=wb.id,
                    latitude=rep_lat,
                    longitude=rep_lng,
                    location=point_wkt,
                    contamination_type=report_data["contamination_type"],
                    reporter_name=report_data["reporter_name"],
                    notes=report_data["notes"],
                    forel_ule_index=report_data["forel_ule_index"],
                    forel_ule_color=report_data["forel_ule_color"],
                    algae_percentage=report_data["algae_percentage"],
                    foam_detected=report_data["foam_detected"],
                    foam_coverage_pct=report_data["foam_coverage_pct"],
                    turbidity_score=report_data["turbidity_score"],
                    composite_score=report_data["composite_score"],
                    risk_level=report_data["risk_level"],
                    created_at=report_time,
                )
                db.add(report)
                total_reports += 1

            # Update water body report count
            wb.total_reports = num_reports
            wb.last_report_at = now - timedelta(hours=random.uniform(1, 48))

        print(f"  ✓ {total_reports} reports created")

        # Insert historical risk scores (4 weeks, one per week per water body)
        print(f"\nInserting risk score history...")
        total_history = 0

        for wb, risk_profile in water_body_records:
            profile = RISK_PROFILES[risk_profile]
            base_score = random.uniform(*profile["score_range"])

            for week in range(4):
                week_time = now - timedelta(days=week * 7)
                # Add some trend variation (slight random walk)
                variation = random.uniform(-5, 5)
                week_score = max(0, min(100, base_score + variation))

                if week_score <= 15:
                    level = "low"
                elif week_score <= 35:
                    level = "moderate"
                else:
                    level = "high"

                risk_score = RiskScore(
                    id=str(uuid.uuid4()),
                    water_body_id=wb.id,
                    risk_score=round(week_score, 1),
                    risk_level=level,
                    avg_algae_pct=round(random.uniform(5, 50), 1),
                    avg_foam_coverage=round(random.uniform(0, 20), 1),
                    avg_turbidity=round(random.uniform(20, 80), 1),
                    report_count=random.randint(2, 8),
                    window_start=week_time - timedelta(days=7),
                    window_end=week_time,
                    created_at=week_time,
                )
                db.add(risk_score)
                total_history += 1

        print(f"  ✓ {total_history} historical risk scores created")

        # Commit everything
        db.commit()

        print(f"\n{'=' * 50}")
        print(f"Seed complete!")
        print(f"  Water bodies: {len(WATER_BODIES)}")
        print(f"  Reports: {total_reports}")
        print(f"  Risk history: {total_history}")
        print(f"\nRun the API: uvicorn app.main:app --reload")
        print(f"Swagger UI: http://localhost:8000/docs")

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
