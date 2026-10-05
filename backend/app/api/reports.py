"""
Report API — POST /analyze-water

Accepts a photo + metadata, runs the 7-factor CV analysis pipeline,
matches to nearest water body, stores results, returns full breakdown.
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.report import Report
from app.models.water_body import WaterBody
from app.models.risk_score import RiskScore
from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis
from app.services.water_body_matcher import find_nearest_water_body
from app.services.roboflow_detector import detect_water_quality
from app.services.yolo_detector import detect_water_quality_local
from app.services.satellite import get_satellite_status_for_water_body
from app.services.alerting import create_alert_candidate

import logging

log = logging.getLogger("aquawatch.reports")

router = APIRouter()


def _enrich_report_with_satellite(report_id: str, water_body_id: str):
    """Background task: run the satellite lookup and persist the verdict.

    Opens its OWN DB session — the request-scoped session from Depends(get_db)
    is already closed by the time a BackgroundTask runs. The satellite call
    (cached lake or live Earth Engine point query) can take 15-60s, which is
    exactly why this is off the request path.
    """
    db = SessionLocal()
    try:
        report = db.get(Report, report_id)
        water_body = db.get(WaterBody, water_body_id)
        if report is None or water_body is None:
            return

        status = get_satellite_status_for_water_body(db, water_body)

        report.satellite_ndci = status.get("live_ndci", status.get("ndci_latest"))
        report.satellite_exceeds_clean_baseline = status.get("exceeds_clean_baseline")
        report.satellite_spatial_confidence = status.get("spatial_confidence")
        report.satellite_corroboration = status.get("corroboration")
        report.satellite_mode = status.get("mode")
        report.satellite_status = "done" if status.get("available") else "unavailable"
        report.satellite_checked_at = datetime.now(timezone.utc)
        db.commit()
        log.info(f"satellite enrichment {report_id}: "
                 f"status={report.satellite_status} mode={report.satellite_mode} "
                 f"corroboration={report.satellite_corroboration}")

        # Authority alerting (original-vision feature): for HIGH-risk reports,
        # create a human-review alert candidate once the satellite verdict is
        # known. Isolated so it can never break satellite enrichment, and it
        # NEVER auto-sends — an operator confirms via POST /alerts/{id}/send.
        try:
            alert = create_alert_candidate(db, report, water_body)
            if alert is not None:
                db.commit()
                log.info(f"alert candidate {alert.id} queued (status=pending_review)")
        except Exception as aexc:  # noqa: BLE001
            db.rollback()
            log.warning(f"alert-candidate creation failed for {report_id}: {aexc}")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.warning(f"satellite enrichment failed for {report_id}: {exc}")
        try:
            report = db.get(Report, report_id)
            if report is not None:
                report.satellite_status = "error"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _satellite_verdict(report: Report) -> dict:
    """Serialize a report's satellite columns into a verdict payload."""
    return {
        "status": report.satellite_status,
        "ndci": report.satellite_ndci,
        "exceeds_clean_baseline": report.satellite_exceeds_clean_baseline,
        "spatial_confidence": report.satellite_spatial_confidence,
        "corroboration": report.satellite_corroboration,
        "mode": report.satellite_mode,
        "checked_at": report.satellite_checked_at.isoformat()
        if report.satellite_checked_at else None,
    }

# Max image size: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# EfficientNet model (lazy loaded)
_eff_model = None
_eff_idx_to_class = None


def _load_efficientnet():
    """Lazy-load EfficientNet model."""
    global _eff_model, _eff_idx_to_class
    if _eff_model is not None:
        return

    import torch
    import torch.nn as nn
    from torchvision import models as tv_models

    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "models", "efficientnet_water_quality.pt"
    )

    if not os.path.exists(model_path):
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)

    model = tv_models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(model.classifier[1].in_features, 2),
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    model = model.to(device)

    _eff_model = model
    _eff_idx_to_class = {v: k for k, v in checkpoint['class_to_idx'].items()}


def _run_efficientnet(image_bytes: bytes) -> dict:
    """Run EfficientNet on image bytes."""
    import torch
    from torchvision import transforms
    from PIL import Image
    import io

    _load_efficientnet()

    if _eff_model is None:
        return {"available": False, "prediction": "unknown", "confidence": 0.0, "bad_probability": 0.0}

    try:
        device = next(_eff_model.parameters()).device
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = _eff_model(img_tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probs, 1)

        pred_class = _eff_idx_to_class[predicted.item()]
        return {
            "available": True,
            "prediction": pred_class,
            "confidence": round(confidence.item(), 3),
            "bad_probability": round(float(probs[0][0].item()), 3),
        }
    except Exception as e:
        return {"available": False, "prediction": "unknown", "confidence": 0.0, "bad_probability": 0.0}

# Max image size: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# Valid contamination types
VALID_CONTAMINATION_TYPES = {
    "industrial_discharge", "sewage", "algal_bloom", "solid_waste",
    "agricultural_runoff", "fish_kill", "foam", "oil_spill", "others",
}


@router.post("/analyze-water", status_code=201)
async def analyze_water(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Photo of water body (JPEG/PNG, max 10MB)"),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    contamination_type: str = Form(...),
    reporter_name: str = Form(None),
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Submit a water body photo for analysis.

    Accepts multipart/form-data with an image file and metadata fields.
    Runs 7-factor CV analysis, finds nearest water body, stores report,
    and returns the full analysis breakdown.
    """
    # Validate contamination type
    if contamination_type not in VALID_CONTAMINATION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid contamination_type. Must be one of: {', '.join(sorted(VALID_CONTAMINATION_TYPES))}",
        )

    # Validate image content type
    if image.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(
            status_code=400,
            detail="Image must be JPEG or PNG format.",
        )

    # Read image bytes
    image_bytes = await image.read()

    # Check size
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)}MB.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Image file is empty.",
        )

    # Run CV analysis pipeline
    try:
        cv_results = analyze_image(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run Roboflow drone model (DISABLED - too slow, adds network latency)
    # ml_result = detect_water_quality(image_bytes)
    ml_result = {"ml_available": False, "pollution_confidence": 0.0, "summary": "Disabled for speed"}

    # Run local YOLO model (trained on ground-level river photos)
    yolo_result = detect_water_quality_local(image_bytes)

    # Run EfficientNet binary classifier (99.8% accuracy on citizen photos)
    eff_result = _run_efficientnet(image_bytes)

    # Calculate base risk score from CV pipeline
    risk_result = calculate_risk_from_analysis(cv_results)

    # === SCORING LOGIC: EfficientNet is PRIMARY authority ===

    # EfficientNet decides if water is good or bad
    eff_says_bad = (
        eff_result["available"]
        and eff_result["prediction"] == "bad"
        and eff_result["confidence"] > 0.70
    )
    eff_says_good = (
        eff_result["available"]
        and eff_result["prediction"] == "good"
        and eff_result["confidence"] > 0.85
    )

    if eff_says_bad:
        # EfficientNet confirms pollution — apply all boosts
        # EfficientNet boost
        eff_boost = eff_result["bad_probability"] * 25  # up to +25
        risk_result["composite_score"] = round(
            min(100.0, risk_result["composite_score"] + eff_boost), 1
        )

        # YOLO boost (only when EfficientNet agrees it's bad)
        if yolo_result["yolo_available"]:
            if yolo_result["prediction"] == "polluted":
                yolo_boost = yolo_result["confidence"] * 30
                risk_result["composite_score"] = round(
                    min(100.0, risk_result["composite_score"] + yolo_boost), 1
                )
            elif yolo_result["prediction"] == "turbid":
                yolo_boost = yolo_result["confidence"] * 15
                risk_result["composite_score"] = round(
                    min(100.0, risk_result["composite_score"] + yolo_boost), 1
                )

        # Roboflow boost
        if ml_result["ml_available"] and ml_result["pollution_confidence"] > 0.5:
            ml_boost = ml_result["pollution_confidence"] * 15
            risk_result["composite_score"] = round(
                min(100.0, risk_result["composite_score"] + ml_boost), 1
            )

    elif eff_says_good:
        # EfficientNet says water is clean — DO NOT let YOLO override
        # Only CV pipeline score applies (no model boosts)
        pass

    else:
        # EfficientNet is uncertain — use YOLO as tiebreaker
        if yolo_result["yolo_available"]:
            if yolo_result["prediction"] == "polluted" and yolo_result["confidence"] > 0.7:
                yolo_boost = yolo_result["confidence"] * 20
                risk_result["composite_score"] = round(
                    min(100.0, risk_result["composite_score"] + yolo_boost), 1
                )
            elif yolo_result["prediction"] == "turbid" and yolo_result["confidence"] > 0.7:
                yolo_boost = yolo_result["confidence"] * 10
                risk_result["composite_score"] = round(
                    min(100.0, risk_result["composite_score"] + yolo_boost), 1
                )

    # --- Safety net: strong CV indicators override everything ---
    cv_foam = float(cv_results["foam"]["foam_coverage_percentage"])
    cv_debris = float(cv_results["surface_debris"]["contour_density"])
    cv_algae = float(cv_results["algae"]["algae_percentage"])

    strong_cv_signal = (cv_foam > 30 or cv_debris > 30 or cv_algae > 50)
    if strong_cv_signal and risk_result["composite_score"] < 36:
        min_score = 36.0 + (cv_foam * 0.15) + (cv_debris * 0.1)
        risk_result["composite_score"] = round(min(100.0, max(risk_result["composite_score"], min_score)), 1)

    # Reclassify risk level after all boosts applied
    from app.services.risk_scoring import classify_risk_level
    risk_result["risk_level"] = classify_risk_level(risk_result["composite_score"])

    # Find nearest water body (or create new one)
    water_body, distance_meters = find_nearest_water_body(db, latitude, longitude)

    # Create report record
    point_wkt = f"SRID=4326;POINT({longitude} {latitude})"
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    report = Report(
        id=report_id,
        water_body_id=water_body.id,
        latitude=latitude,
        longitude=longitude,
        location=point_wkt,
        contamination_type=contamination_type,
        reporter_name=reporter_name,
        notes=notes,
        forel_ule_index=int(cv_results["forel_ule"]["fu_index"]),
        forel_ule_color=cv_results["forel_ule"]["fu_color_name"],
        algae_percentage=float(cv_results["algae"]["algae_percentage"]),
        foam_detected=bool(cv_results["foam"]["foam_detected"]),
        foam_coverage_pct=float(cv_results["foam"]["foam_coverage_percentage"]),
        turbidity_score=float(cv_results["turbidity"]["turbidity_score"]),
        composite_score=float(risk_result["composite_score"]),
        risk_level=risk_result["risk_level"],
        satellite_status="processing",   # background task will fill the verdict
        created_at=now,
    )
    db.add(report)

    # Update water body stats
    water_body.total_reports += 1
    water_body.last_report_at = now
    water_body.current_risk_score = float(risk_result["composite_score"])
    water_body.current_risk_level = risk_result["risk_level"]
    water_body.updated_at = now

    # Store risk score snapshot
    risk_score_record = RiskScore(
        id=str(uuid.uuid4()),
        water_body_id=water_body.id,
        risk_score=float(risk_result["composite_score"]),
        risk_level=risk_result["risk_level"],
        avg_algae_pct=float(cv_results["algae"]["algae_percentage"]),
        avg_foam_coverage=float(cv_results["foam"]["foam_coverage_percentage"]),
        avg_turbidity=float(cv_results["turbidity"]["turbidity_score"]),
        report_count=water_body.total_reports,
        window_start=now,
        window_end=now,
        created_at=now,
    )
    db.add(risk_score_record)

    # Commit all changes
    db.commit()

    # Dispatch the satellite lookup as a background task (off the request path).
    background_tasks.add_task(_enrich_report_with_satellite, report_id, water_body.id)

    # Build response
    return {
        "report_id": report_id,
        "status": "processing_satellite",
        "satellite_status": "processing",
        "water_body": {
            "id": water_body.id,
            "name": water_body.name,
            "distance_meters": round(distance_meters, 1),
        },
        "analysis": {
            "forel_ule": cv_results["forel_ule"],
            "algae": cv_results["algae"],
            "foam": cv_results["foam"],
            "turbidity": cv_results["turbidity"],
            "oil_sheen": cv_results["oil_sheen"],
            "color_abnormality": cv_results["color_abnormality"],
            "surface_debris": cv_results["surface_debris"],
        },
        "ml_detection": ml_result,
        "yolo_detection": yolo_result,
        "efficientnet": eff_result,
        "risk": risk_result,
        "created_at": now.isoformat(),
    }


def _report_payload(r: Report) -> dict:
    """Serialize a Report row (including the satellite verdict) for GET responses."""
    return {
        "id": r.id,
        "water_body_id": r.water_body_id,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "contamination_type": r.contamination_type,
        "reporter_name": r.reporter_name,
        "notes": r.notes,
        "forel_ule_index": r.forel_ule_index,
        "algae_percentage": r.algae_percentage,
        "foam_detected": r.foam_detected,
        "turbidity_score": r.turbidity_score,
        "composite_score": r.composite_score,
        "risk_level": r.risk_level,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "satellite_verdict": _satellite_verdict(r),
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """
    Fetch a single report, including the satellite corroboration verdict.

    Right after submission `satellite_verdict.status` is "processing"; poll this
    endpoint until it becomes "done" / "unavailable" / "error".
    """
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_payload(report)


@router.get("/reports")
async def list_reports(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List recent reports (most recent first), each with its satellite verdict."""
    limit = max(1, min(limit, 100))
    total = db.query(Report).count()
    rows = (db.query(Report)
            .order_by(Report.created_at.desc())
            .offset(max(0, offset))
            .limit(limit)
            .all())
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "reports": [_report_payload(r) for r in rows],
    }
