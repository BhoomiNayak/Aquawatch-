"""
Authority alerting service (original-vision feature).

Pipeline role: when a report is classified HIGH risk, create an alert
*candidate* addressed to the responsible authority. The candidate is NOT sent
automatically — an operator confirms it via the API. Sending is dry-run by
default (composes and stores the message; never dispatches) and only performs a
real SMTP send when ALERTS_DRY_RUN=false and SMTP is configured.

Design rationale (honest):
- The ground image classifier is unreliable out-of-distribution (ROC-AUC ~0.49
  on the Indian benchmark), so alerts must never auto-fire to real authorities.
  Human review (pending_review -> send/dismiss) is mandatory, and the satellite
  corroboration verdict is surfaced to help the reviewer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.alert import Alert
from app.models.authority import Authority
from app.models.report import Report
from app.models.water_body import WaterBody

log = logging.getLogger("aquawatch.alerting")

_LEVEL_ORDER = {"low": 0, "moderate": 1, "high": 2}


def _meets_threshold(risk_level: str) -> bool:
    s = get_settings()
    return _LEVEL_ORDER.get(risk_level, 0) >= _LEVEL_ORDER.get(s.alerts_min_level, 2)


def match_authority(db: Session, water_body: WaterBody) -> Authority | None:
    """Find the responsible authority: exact city/state match, else default."""
    city = (getattr(water_body, "city", "") or "").strip().lower()
    state = (getattr(water_body, "state", "") or "").strip().lower()

    authorities = db.query(Authority).all()
    for a in authorities:
        j = (a.jurisdiction or "").strip().lower()
        if j and (j == city or j == state):
            return a
    # fallback to a default authority if one is configured
    for a in authorities:
        if a.is_default:
            return a
    return None


def compose_message(report: Report, water_body: WaterBody,
                    authority: Authority | None) -> tuple[str, str]:
    """Return (subject, body) for the alert e-mail."""
    name = water_body.name or "an unnamed water body"
    subject = f"[AquaWatch] {report.risk_level.upper()} pollution risk reported — {name}"
    sat = report.satellite_corroboration or "unavailable"
    lines = [
        f"Dear {authority.name if authority else 'Water Quality Authority'},",
        "",
        "A citizen report submitted via AquaWatch indicates a HIGH pollution "
        "risk at the following location. This is a preliminary, appearance-based "
        "screening alert and requires on-site verification.",
        "",
        f"  Water body     : {name}",
        f"  Location       : {water_body.city}, {water_body.state} "
        f"({report.latitude:.5f}, {report.longitude:.5f})",
        f"  Risk level     : {report.risk_level.upper()}  (composite score "
        f"{report.composite_score:.1f}/100)",
        f"  Contamination  : {report.contamination_type}",
        f"  Satellite NDCI corroboration : {sat}",
        f"  Reported at    : {report.created_at.isoformat() if report.created_at else 'n/a'}",
        f"  Report ID      : {report.id}",
    ]
    if report.notes:
        lines += ["", f"  Reporter notes : {report.notes}"]
    lines += [
        "",
        "Caveat: AquaWatch performs visual/appearance-based screening and a "
        "coarse satellite chlorophyll check. It is not a substitute for "
        "laboratory water-quality testing. Please treat this as a lead for "
        "field inspection, not a confirmed measurement.",
        "",
        "— AquaWatch (automated, operator-reviewed alert)",
    ]
    return subject, "\n".join(lines)


def create_alert_candidate(db: Session, report: Report,
                           water_body: WaterBody) -> Alert | None:
    """Create a pending_review alert for a HIGH-risk report. Never sends."""
    s = get_settings()
    if not s.alerts_enabled or not _meets_threshold(report.risk_level):
        return None

    authority = match_authority(db, water_body)
    subject, body = compose_message(report, water_body, authority)
    alert = Alert(
        id=str(uuid.uuid4()),
        report_id=report.id,
        water_body_id=water_body.id,
        authority_id=authority.id if authority else None,
        risk_level=report.risk_level,
        composite_score=report.composite_score,
        satellite_corroboration=report.satellite_corroboration,
        status="pending_review",
        channel="email",
        recipient=authority.email if authority else None,
        subject=subject,
        body=body,
        send_note=None if authority else "No matching authority; assign before sending.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.flush()
    log.info(f"alert candidate {alert.id} created for report {report.id} "
             f"(authority={authority.name if authority else 'UNASSIGNED'})")
    return alert


def send_alert(db: Session, alert: Alert) -> dict:
    """Operator-confirmed send. Dry-run by default; real SMTP only if configured."""
    s = get_settings()
    if alert.status == "sent":
        return {"status": "sent", "note": "already sent", "dry_run": False}
    if not alert.recipient:
        return {"status": "error", "note": "no recipient — assign an authority first"}

    if s.alerts_dry_run or not s.smtp_host:
        alert.status = "sent"
        alert.sent_at = datetime.now(timezone.utc)
        alert.send_note = ("DRY-RUN: message composed and stored, not dispatched "
                           "(set ALERTS_DRY_RUN=false and configure SMTP to send).")
        db.flush()
        log.info(f"alert {alert.id} DRY-RUN 'sent' to {alert.recipient}")
        return {"status": "sent", "dry_run": True, "recipient": alert.recipient,
                "note": alert.send_note}

    # Real send
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(alert.body or "")
        msg["Subject"] = alert.subject or "[AquaWatch] Pollution alert"
        msg["From"] = s.smtp_from
        msg["To"] = alert.recipient
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
            server.starttls()
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from, [alert.recipient], msg.as_string())
        alert.status = "sent"
        alert.sent_at = datetime.now(timezone.utc)
        alert.send_note = f"Sent via SMTP {s.smtp_host} to {alert.recipient}."
        db.flush()
        return {"status": "sent", "dry_run": False, "recipient": alert.recipient}
    except Exception as exc:  # noqa: BLE001
        alert.send_note = f"SMTP send failed: {exc}"
        db.flush()
        log.warning(f"alert {alert.id} send failed: {exc}")
        return {"status": "error", "note": alert.send_note}
