"""
Report API — POST /analyze-water

Accepts a photo + metadata, runs the 7-factor CV analysis pipeline,
matches to nearest water body, stores results, returns full breakdown.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import Report
from app.models.water_body import WaterBody
from app.models.risk_score import RiskScore
from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis
from app.services.water_body_matcher import find_nearest_water_body
from app.services.roboflow_detector import detect_water_quality
from app.services.yolo_detector import detect_water_quality_local

router = APIRouter()

# Max image size: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# Valid contamination types
VALID_CONTAMINATION_TYPES = {
    "industrial_discharge", "sewage", "algal_bloom", "solid_waste",
    "agricultural_runoff", "fish_kill", "foam", "oil_spill", "others",
}


@router.post("/analyze-water", status_code=201)
async def analyze_water(
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

    # Run Roboflow drone model (cloud API, works better on overhead shots)
    ml_result = detect_water_quality(image_bytes)

    # Run local YOLO model (trained on ground-level river photos)
    yolo_result = detect_water_quality_local(image_bytes)

    # Calculate base risk score from CV pipeline
    risk_result = calculate_risk_from_analysis(cv_results)

    # --- Boost 1: Roboflow drone model ---
    if ml_result["ml_available"] and ml_result["pollution_confidence"] > 0.5:
        ml_boost = ml_result["pollution_confidence"] * 20  # up to +20 points
        risk_result["composite_score"] = round(
            min(100.0, risk_result["composite_score"] + ml_boost), 1
        )

    # --- Boost 2: Local YOLO model (ground-level river classifier) ---
    # This is our primary ML signal since it's trained on citizen-style photos
    if yolo_result["yolo_available"]:
        prediction = yolo_result["prediction"]
        confidence = yolo_result["confidence"]

        if prediction == "polluted":
            # Strong signal: push toward HIGH risk
            yolo_boost = confidence * 35  # up to +35 points
            risk_result["composite_score"] = round(
                min(100.0, risk_result["composite_score"] + yolo_boost), 1
            )
        elif prediction == "turbid":
            # Moderate signal: push toward MODERATE
            yolo_boost = confidence * 18  # up to +18 points
            risk_result["composite_score"] = round(
                min(100.0, risk_result["composite_score"] + yolo_boost), 1
            )
        # "clean" prediction: no boost, trust CV pipeline as-is

    # --- Safety net: if CV detects strong pollution indicators but YOLO missed it ---
    # Only override if YOLO isn't highly confident it's clean
    cv_foam = float(cv_results["foam"]["foam_coverage_percentage"])
    cv_debris = float(cv_results["surface_debris"]["contour_density"])
    cv_algae = float(cv_results["algae"]["algae_percentage"])
    cv_oil = float(cv_results["oil_sheen"]["oil_coverage_percentage"])

    yolo_says_clean = (
        yolo_result["yolo_available"]
        and yolo_result["prediction"] == "clean"
        and yolo_result["confidence"] > 0.90
    )

    strong_cv_signal = (cv_foam > 25 or cv_debris > 25 or cv_algae > 40 or cv_oil > 10)
    if strong_cv_signal and not yolo_says_clean and risk_result["composite_score"] < 35:
        # Force minimum HIGH score when obvious pollution is detected AND YOLO doesn't strongly disagree
        min_score = 36.0 + (cv_foam * 0.2) + (cv_debris * 0.15)
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

    # Build response
    return {
        "report_id": report_id,
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
        "risk": risk_result,
        "created_at": now.isoformat(),
    }
