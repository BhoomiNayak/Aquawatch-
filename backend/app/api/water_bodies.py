"""
Water Bodies API — GET endpoints for dashboard.

- GET /water-bodies — list all with current risk
- GET /water-bodies/{id} — detail with breakdown
- GET /water-bodies/{id}/history — risk score timeline
- GET /water-bodies/{id}/reports — individual reports
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.database import get_db
from app.models.water_body import WaterBody
from app.models.report import Report
from app.models.risk_score import RiskScore

router = APIRouter()


@router.get("/water-bodies")
async def list_water_bodies(
    risk_level: Optional[str] = Query(None, description="Filter: low, moderate, high"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all water bodies with current risk scores."""
    query = db.query(WaterBody)

    # Filter by risk level if provided
    if risk_level and risk_level in ("low", "moderate", "high"):
        query = query.filter(WaterBody.current_risk_level == risk_level)

    # Get total count
    total = query.count()

    # Get water bodies
    water_bodies = query.order_by(
        WaterBody.current_risk_score.desc()
    ).offset(offset).limit(limit).all()

    # Calculate reports_last_7_days for each
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    result = []
    for wb in water_bodies:
        recent_count = db.query(Report).filter(
            Report.water_body_id == wb.id,
            Report.created_at >= seven_days_ago,
        ).count()

        result.append({
            "id": wb.id,
            "name": wb.name,
            "latitude": wb.latitude,
            "longitude": wb.longitude,
            "type": wb.type,
            "city": wb.city,
            "risk_level": wb.current_risk_level,
            "risk_score": wb.current_risk_score,
            "total_reports": wb.total_reports,
            "reports_last_7_days": recent_count,
            "last_report_at": wb.last_report_at.isoformat() if wb.last_report_at else None,
        })

    return {
        "count": total,
        "water_bodies": result,
    }


@router.get("/water-bodies/{water_body_id}")
async def get_water_body_detail(
    water_body_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information about a single water body."""
    water_body = db.query(WaterBody).filter(WaterBody.id == water_body_id).first()

    if not water_body:
        raise HTTPException(status_code=404, detail="Water body not found")

    # Get reports in last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = db.query(Report).filter(
        Report.water_body_id == water_body_id,
        Report.created_at >= seven_days_ago,
    ).count()

    # Get latest report for analysis data
    latest_report = db.query(Report).filter(
        Report.water_body_id == water_body_id,
    ).order_by(Report.created_at.desc()).first()

    latest_analysis = None
    if latest_report:
        latest_analysis = {
            "forel_ule_index": latest_report.forel_ule_index,
            "algae_percentage": latest_report.algae_percentage,
            "foam_detected": latest_report.foam_detected,
            "foam_coverage_percentage": latest_report.foam_coverage_pct,
            "turbidity_score": latest_report.turbidity_score,
        }

    # Get contamination type breakdown
    contamination_counts = db.query(
        Report.contamination_type,
        func.count(Report.id).label("count"),
    ).filter(
        Report.water_body_id == water_body_id,
    ).group_by(Report.contamination_type).all()

    breakdown = {}
    for ct, count in contamination_counts:
        breakdown[ct] = count

    return {
        "id": water_body.id,
        "name": water_body.name,
        "latitude": water_body.latitude,
        "longitude": water_body.longitude,
        "type": water_body.type,
        "city": water_body.city,
        "state": water_body.state,
        "risk_level": water_body.current_risk_level,
        "risk_score": water_body.current_risk_score,
        "total_reports": water_body.total_reports,
        "reports_last_7_days": recent_count,
        "latest_analysis": latest_analysis,
        "contamination_breakdown": breakdown,
        "last_report_at": water_body.last_report_at.isoformat() if water_body.last_report_at else None,
        "created_at": water_body.created_at.isoformat() if water_body.created_at else None,
    }


@router.get("/water-bodies/{water_body_id}/history")
async def get_water_body_history(
    water_body_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get historical risk scores for trend visualization."""
    water_body = db.query(WaterBody).filter(WaterBody.id == water_body_id).first()

    if not water_body:
        raise HTTPException(status_code=404, detail="Water body not found")

    # Get risk scores within the time window
    since = datetime.now(timezone.utc) - timedelta(days=days)

    risk_scores = db.query(RiskScore).filter(
        RiskScore.water_body_id == water_body_id,
        RiskScore.created_at >= since,
    ).order_by(RiskScore.created_at.desc()).all()

    history = []
    for rs in risk_scores:
        history.append({
            "date": rs.created_at.strftime("%Y-%m-%d") if rs.created_at else None,
            "risk_score": rs.risk_score,
            "risk_level": rs.risk_level,
            "report_count": rs.report_count,
            "avg_algae": rs.avg_algae_pct,
            "avg_turbidity": rs.avg_turbidity,
        })

    return {
        "water_body_id": water_body.id,
        "water_body_name": water_body.name,
        "history": history,
    }


@router.get("/water-bodies/{water_body_id}/reports")
async def get_water_body_reports(
    water_body_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get individual reports for a water body."""
    water_body = db.query(WaterBody).filter(WaterBody.id == water_body_id).first()

    if not water_body:
        raise HTTPException(status_code=404, detail="Water body not found")

    # Get total count
    total = db.query(Report).filter(Report.water_body_id == water_body_id).count()

    # Get reports
    reports = db.query(Report).filter(
        Report.water_body_id == water_body_id,
    ).order_by(Report.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for r in reports:
        result.append({
            "id": r.id,
            "contamination_type": r.contamination_type,
            "reporter_name": r.reporter_name,
            "notes": r.notes,
            "composite_score": r.composite_score,
            "risk_level": r.risk_level,
            "forel_ule_index": r.forel_ule_index,
            "algae_percentage": r.algae_percentage,
            "foam_detected": r.foam_detected,
            "turbidity_score": r.turbidity_score,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "water_body_id": water_body.id,
        "total": total,
        "reports": result,
    }
