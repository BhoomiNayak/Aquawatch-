"""
Water Body Matcher Service.

Uses PostGIS spatial queries to find the nearest water body
within 500 meters of a given GPS coordinate.

If no water body is found, creates a new "Unnamed Water Body" entry.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.water_body import WaterBody


# Maximum distance in meters to match a report to a water body
MAX_MATCH_DISTANCE_METERS = 500


def find_nearest_water_body(
    db: Session, latitude: float, longitude: float
) -> tuple[WaterBody, float]:
    """
    Find the nearest water body within 500m of the given coordinates.

    If none found, creates a new unnamed water body at those coordinates.

    Args:
        db: Database session
        latitude: Report latitude
        longitude: Report longitude

    Returns:
        Tuple of (WaterBody instance, distance_in_meters)
    """
    # PostGIS query: find nearest water body within 500m
    # Uses geography cast for meter-based distance calculation
    point_wkt = f"POINT({longitude} {latitude})"

    result = db.execute(
        text("""
            SELECT id, name,
                   ST_Distance(
                       location::geography,
                       ST_SetSRID(ST_GeomFromText(:point), 4326)::geography
                   ) as distance_meters
            FROM water_bodies
            WHERE ST_DWithin(
                location::geography,
                ST_SetSRID(ST_GeomFromText(:point), 4326)::geography,
                :max_distance
            )
            ORDER BY distance_meters
            LIMIT 1
        """),
        {
            "point": point_wkt,
            "max_distance": MAX_MATCH_DISTANCE_METERS,
        },
    ).fetchone()

    if result:
        # Found a nearby water body
        water_body = db.query(WaterBody).filter(WaterBody.id == result.id).first()
        return water_body, result.distance_meters
    else:
        # No water body nearby — create a new one
        water_body = create_unnamed_water_body(db, latitude, longitude)
        return water_body, 0.0


def create_unnamed_water_body(
    db: Session, latitude: float, longitude: float
) -> WaterBody:
    """
    Create a new unnamed water body at the given coordinates.

    Called when a report is submitted far from any known water body.
    """
    point_wkt = f"SRID=4326;POINT({longitude} {latitude})"

    water_body = WaterBody(
        id=str(uuid.uuid4()),
        name=f"Unnamed Water Body ({latitude:.4f}, {longitude:.4f})",
        latitude=latitude,
        longitude=longitude,
        location=point_wkt,
        type="unknown",
        city="Unknown",
        state="Unknown",
        current_risk_score=0.0,
        current_risk_level="low",
        total_reports=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(water_body)
    db.flush()  # Get the ID without committing

    return water_body
