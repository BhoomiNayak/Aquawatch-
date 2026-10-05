"""
Alerts API — authority notification (human-in-the-loop).

Endpoints:
  GET  /authorities              list configured authorities
  GET  /alerts                   list alerts (filter by status)
  GET  /alerts/{id}              one alert incl. composed message
  POST /alerts/{id}/send         operator confirms -> send (dry-run by default)
  POST /alerts/{id}/assign       set/override the authority (recipient)
  POST /alerts/{id}/dismiss      mark as false alarm
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.authority import Authority
from app.services.alerting import send_alert

router = APIRouter()


def _alert_payload(a: Alert) -> dict:
    return {
        "id": a.id,
        "report_id": a.report_id,
        "water_body_id": a.water_body_id,
        "authority_id": a.authority_id,
        "recipient": a.recipient,
        "risk_level": a.risk_level,
        "composite_score": a.composite_score,
        "satellite_corroboration": a.satellite_corroboration,
        "status": a.status,
        "channel": a.channel,
        "subject": a.subject,
        "body": a.body,
        "send_note": a.send_note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "sent_at": a.sent_at.isoformat() if a.sent_at else None,
    }


@router.get("/authorities")
async def list_authorities(db: Session = Depends(get_db)):
    rows = db.query(Authority).all()
    return {
        "total": len(rows),
        "authorities": [
            {"id": a.id, "name": a.name, "email": a.email,
             "website": a.website, "verified": a.verified,
             "jurisdiction": a.jurisdiction, "is_default": a.is_default}
            for a in rows
        ],
    }


@router.get("/alerts")
async def list_alerts(status: str | None = None, limit: int = 50,
                      db: Session = Depends(get_db)):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    rows = q.order_by(Alert.created_at.desc()).limit(max(1, min(limit, 200))).all()
    return {"total": len(rows), "alerts": [_alert_payload(a) for a in rows]}


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_payload(a)


@router.post("/alerts/{alert_id}/assign")
async def assign_authority(alert_id: str, authority_id: str,
                           db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    auth = db.get(Authority, authority_id)
    if auth is None:
        raise HTTPException(status_code=404, detail="Authority not found")
    a.authority_id = auth.id
    a.recipient = auth.email
    a.send_note = None
    db.commit()
    return _alert_payload(a)


@router.post("/alerts/{alert_id}/send", status_code=200)
async def send(alert_id: str, db: Session = Depends(get_db)):
    """Operator confirms dispatch. Dry-run unless SMTP configured + ALERTS_DRY_RUN=false."""
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if a.status == "dismissed":
        raise HTTPException(status_code=409, detail="Alert was dismissed")
    result = send_alert(db, a)
    db.commit()
    return {"alert": _alert_payload(a), "result": result}


@router.post("/alerts/{alert_id}/dismiss", status_code=200)
async def dismiss(alert_id: str, reason: str | None = None,
                  db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    a.status = "dismissed"
    a.send_note = f"dismissed: {reason}" if reason else "dismissed (false alarm)"
    db.commit()
    return _alert_payload(a)
