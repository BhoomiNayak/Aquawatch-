"""
Roboflow Water Quality Detection Service.

Uses the "drone-water-quality-monitor/1" model to classify water regions
as Clean, Algae, or Polluted via instance segmentation.

This adds an ML-based classification on top of our classical CV pipeline.
"""

import tempfile
import os
import logging

from inference_sdk import InferenceHTTPClient

from app.config import get_settings

logger = logging.getLogger("aquawatch.roboflow")


def detect_water_quality(image_bytes: bytes) -> dict:
    """
    Run Roboflow model inference on water image.

    Args:
        image_bytes: Raw JPEG/PNG bytes

    Returns:
        {
            "ml_available": bool,
            "predictions": [
                {
                    "class": "Polluted" | "Algae" | "Clean",
                    "confidence": 0.85,
                    "area_percentage": 45.2
                }
            ],
            "dominant_class": "Polluted" | "Algae" | "Clean" | "Unknown",
            "pollution_confidence": 0.0-1.0,
            "summary": "Polluted (85% confidence, 45% of image)"
        }
    """
    settings = get_settings()

    if not settings.roboflow_api_key:
        logger.warning("Roboflow API key not set - skipping ML detection")
        return _empty_result("No API key configured")

    try:
        client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key=settings.roboflow_api_key,
        )

        # Write image to temp file (inference_sdk needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(image_bytes)
            temp_path = f.name

        try:
            result = client.infer(temp_path, model_id=settings.roboflow_model_id)
        finally:
            os.unlink(temp_path)

        # Parse predictions
        predictions = []
        if "predictions" in result:
            for pred in result["predictions"]:
                predictions.append({
                    "class": pred.get("class", "Unknown"),
                    "confidence": round(pred.get("confidence", 0), 3),
                })

        if not predictions:
            return _empty_result("No objects detected")

        # Find dominant class (highest confidence)
        best = max(predictions, key=lambda x: x["confidence"])
        dominant_class = best["class"]
        top_confidence = best["confidence"]

        # Calculate pollution confidence
        # "Polluted" or "Algae" = pollution indicator
        pollution_preds = [p for p in predictions if p["class"] in ("Polluted", "polluted", "Algae", "algae")]
        if pollution_preds:
            pollution_confidence = max(p["confidence"] for p in pollution_preds)
        else:
            pollution_confidence = 0.0

        # Count class occurrences
        class_counts = {}
        for p in predictions:
            cls = p["class"]
            class_counts[cls] = class_counts.get(cls, 0) + 1

        summary = f"{dominant_class} ({top_confidence*100:.0f}% confidence, {len(predictions)} regions detected)"

        return {
            "ml_available": True,
            "predictions_count": len(predictions),
            "class_counts": class_counts,
            "dominant_class": dominant_class,
            "dominant_confidence": top_confidence,
            "pollution_confidence": pollution_confidence,
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Roboflow inference failed: {e}")
        return _empty_result(f"ML inference failed: {str(e)}")


def _empty_result(reason: str) -> dict:
    """Return empty result when ML detection is unavailable."""
    return {
        "ml_available": False,
        "predictions_count": 0,
        "class_counts": {},
        "dominant_class": "Unknown",
        "dominant_confidence": 0.0,
        "pollution_confidence": 0.0,
        "summary": reason,
    }
