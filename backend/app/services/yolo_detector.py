"""
Local YOLO Water Quality Detector.

Uses our trained YOLOv8n-seg model to classify water as clean/turbid/polluted.
Runs locally on GPU — no API calls needed.
"""

import os
import tempfile
import logging

import numpy as np

logger = logging.getLogger("aquawatch.yolo")

# Lazy-load model (only loads once on first call)
_model = None
_model_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "runs", "segment", "runs", "segment", "aquawatch", "weights", "best.pt"
)


def _get_model():
    """Lazy-load YOLO model."""
    global _model
    if _model is None:
        if not os.path.exists(_model_path):
            logger.warning(f"YOLO model not found at {_model_path}")
            return None
        try:
            from ultralytics import YOLO
            _model = YOLO(_model_path)
            logger.info(f"YOLO model loaded from {_model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return None
    return _model


def detect_water_quality_local(image_bytes: bytes) -> dict:
    """
    Run local YOLO model on water image.

    Args:
        image_bytes: Raw JPEG/PNG bytes

    Returns:
        {
            "yolo_available": bool,
            "prediction": "clean" | "turbid" | "polluted" | "unknown",
            "confidence": float (0-1),
            "all_detections": [{"class": str, "confidence": float}],
            "summary": str
        }
    """
    model = _get_model()
    if model is None:
        return _empty_result("YOLO model not available")

    try:
        # Write to temp file (YOLO needs file path)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_bytes)
            temp_path = f.name

        try:
            results = model(temp_path, verbose=False)
        finally:
            os.unlink(temp_path)

        r = results[0]

        if r.boxes is None or len(r.boxes) == 0:
            return _empty_result("No water regions detected")

        # Collect all detections
        all_detections = []
        for i in range(len(r.boxes)):
            cls_name = r.names[int(r.boxes.cls[i])]
            conf = float(r.boxes.conf[i])
            all_detections.append({"class": cls_name, "confidence": round(conf, 3)})

        # Primary prediction = highest confidence
        best = max(all_detections, key=lambda x: x["confidence"])
        prediction = best["class"]
        confidence = best["confidence"]

        summary = f"{prediction} ({confidence*100:.0f}% confidence, {len(all_detections)} region(s))"

        return {
            "yolo_available": True,
            "prediction": prediction,
            "confidence": confidence,
            "all_detections": all_detections,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")
        return _empty_result(f"Inference failed: {str(e)}")


def _empty_result(reason: str) -> dict:
    """Return empty result when YOLO is unavailable."""
    return {
        "yolo_available": False,
        "prediction": "unknown",
        "confidence": 0.0,
        "all_detections": [],
        "summary": reason,
    }
