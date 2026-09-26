"""
predict_indian_testset.py
=========================
Runs the FULL AquaWatch pipeline (CV + EfficientNet + YOLO) on all 200
Indian test-set images. Produces:

  1. A prediction CSV (annotator-support: pre-filled suggestion column)
  2. A distribution sanity-check report (are we calling everything polluted?)

This does NOT compute accuracy — there are no ground-truth labels yet.
It is a PREP + SANITY tool only.

Mapping to annotator 3-level scale:
  CV composite score → 0=Low (0-15), 1=Moderate (16-35), 2=High (36-100)
  EfficientNet        → good/bad (binary, shown for reference)
  YOLO                → clean/turbid/polluted (shown for reference)

USAGE:
    cd backend
    python scripts/predict_indian_testset.py

OUTPUTS:
    reports/indian_testset_predictions.csv
    reports/indian_testset_distribution.json
"""

import os
import sys
import csv
import json
import glob
import logging
import io
from collections import Counter

# make app importable
BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis, classify_risk_level
from app.services.yolo_detector import detect_water_quality_local

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("predict_indian")

# ── Paths ─────────────────────────────────────────────────────────────
IMG_DIR   = os.path.join(BASE, "datasets", "IndianWaterDataset", "indian_test_set_200")
META_CSV  = os.path.join(BASE, "datasets", "IndianWaterDataset", "image_metadata.csv")
EFF_MODEL = os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt")
OUT_CSV   = os.path.join(BASE, "reports", "indian_testset_predictions.csv")
OUT_JSON  = os.path.join(BASE, "reports", "indian_testset_distribution.json")


def load_efficientnet(device):
    if not os.path.exists(EFF_MODEL):
        log.warning(f"EfficientNet not found at {EFF_MODEL}")
        return None, None
    ckpt = torch.load(EFF_MODEL, map_location=device, weights_only=False)
    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(nn.Dropout(0.3),
                                     nn.Linear(model.classifier[1].in_features, 2))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval().to(device)
    # Handle both storage formats robustly:
    #   {0: 'bad', 1: 'good'}  (idx->class)  OR  {'bad': 0, 'good': 1} (class->idx)
    c2i = ckpt["class_to_idx"]
    sample_key = next(iter(c2i.keys()))
    if isinstance(sample_key, int) or (isinstance(sample_key, str) and sample_key.isdigit()):
        # already idx -> class
        idx_to_class = {int(k): v for k, v in c2i.items()}
    else:
        # class -> idx, invert it
        idx_to_class = {int(v): k for k, v in c2i.items()}
    log.info(f"EfficientNet loaded (val_acc={ckpt.get('val_acc','?')}) idx_to_class={idx_to_class}")
    return model, idx_to_class


def eff_predict(model, idx_to_class, image_bytes, device, tfm):
    if model is None:
        return {"label": "N/A", "confidence": 0.0}
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    x = tfm(img).unsqueeze(0).to(device)
    with torch.no_grad():
        probs = torch.softmax(model(x), dim=1)
        conf, pred = torch.max(probs, 1)
    return {"label": idx_to_class[pred.item()], "confidence": round(conf.item(), 3)}


def score_to_level(score):
    """Map CV composite score to 3-level annotator scale (0/1/2)."""
    level = classify_risk_level(score)
    return {"low": 0, "moderate": 1, "high": 2}[level], level


def load_metadata():
    """Load existing metadata (image_id, filename, source_category)."""
    meta = {}
    if os.path.exists(META_CSV):
        with open(META_CSV, newline="") as f:
            for row in csv.DictReader(f):
                meta[row["filename"]] = row.get("source_category", "")
    return meta


def main():
    print("=" * 68)
    print("AquaWatch — Indian Test Set Prediction & Sanity Check")
    print("=" * 68)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")

    tfm = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    eff_model, idx_to_class = load_efficientnet(device)
    meta = load_metadata()

    files = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")) +
                   glob.glob(os.path.join(IMG_DIR, "*.jpeg")) +
                   glob.glob(os.path.join(IMG_DIR, "*.png")))
    if not files:
        print(f"\n  No images found in {IMG_DIR}")
        return
    log.info(f"Found {len(files)} images")

    rows = []
    cv_level_counts = Counter()
    eff_counts = Counter()
    yolo_counts = Counter()
    errors = 0

    for i, path in enumerate(files):
        fname = os.path.basename(path)
        if (i + 1) % 25 == 0:
            log.info(f"  Processing {i+1}/{len(files)}...")
        try:
            with open(path, "rb") as fh:
                image_bytes = fh.read()

            cv = analyze_image(image_bytes)
            risk = calculate_risk_from_analysis(cv)
            cv_level_num, cv_level_name = score_to_level(risk["composite_score"])

            eff = eff_predict(eff_model, idx_to_class, image_bytes, device, tfm)
            yolo = detect_water_quality_local(image_bytes)

            cv_level_counts[cv_level_name] += 1
            eff_counts[eff["label"]] += 1
            yolo_counts[yolo["prediction"] if yolo["yolo_available"] else "none"] += 1

            rows.append({
                "filename": fname,
                "source_category": meta.get(fname, ""),
                "cv_score": risk["composite_score"],
                "model_suggested_level": cv_level_num,   # 0/1/2 — annotator helper
                "cv_level_name": cv_level_name,
                "efficientnet": eff["label"],
                "efficientnet_conf": eff["confidence"],
                "yolo": yolo["prediction"] if yolo["yolo_available"] else "none",
                "yolo_conf": round(yolo["confidence"], 3) if yolo["yolo_available"] else 0,
                "algae_pct": cv["algae"]["algae_percentage"],
                "foam_pct": cv["foam"]["foam_coverage_percentage"],
                "oil_pct": cv["oil_sheen"]["oil_coverage_percentage"],
                "debris": cv["surface_debris"]["contour_density"],
                "forel_ule": cv["forel_ule"]["fu_index"],
            })
        except Exception as e:
            errors += 1
            log.warning(f"  Failed {fname}: {e}")

    # ── Write predictions CSV ──────────────────────────────────────
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"Predictions written: {OUT_CSV}")

    # ── Distribution sanity report ─────────────────────────────────
    n = len(rows)
    dist = {
        "total_images": n,
        "errors": errors,
        "cv_level_distribution": dict(cv_level_counts),
        "cv_level_pct": {k: round(v/n*100, 1) for k, v in cv_level_counts.items()},
        "efficientnet_distribution": dict(eff_counts),
        "efficientnet_pct": {k: round(v/n*100, 1) for k, v in eff_counts.items()},
        "yolo_distribution": dict(yolo_counts),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(dist, f, indent=2)

    # ── Terminal summary + sanity flags ────────────────────────────
    print()
    print("=" * 68)
    print("PREDICTION DISTRIBUTION (sanity check)")
    print("=" * 68)
    print(f"  Total images: {n}  (errors: {errors})\n")

    print("  CV composite → 3-level (this is the annotator-support column):")
    for lvl in ["low", "moderate", "high"]:
        c = cv_level_counts.get(lvl, 0)
        bar = "#" * int(c / n * 40)
        print(f"    {lvl:<9} {c:>4} ({c/n*100:>5.1f}%)  {bar}")

    print("\n  EfficientNet (good/bad):")
    for k, c in eff_counts.items():
        print(f"    {k:<9} {c:>4} ({c/n*100:>5.1f}%)")

    print("\n  YOLO (clean/turbid/polluted):")
    for k, c in yolo_counts.items():
        print(f"    {k:<9} {c:>4} ({c/n*100:>5.1f}%)")

    # ── Sanity flags ───────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("SANITY FLAGS")
    print("=" * 68)
    flags = []
    high_pct = cv_level_counts.get("high", 0) / n * 100
    low_pct = cv_level_counts.get("low", 0) / n * 100
    bad_pct = eff_counts.get("bad", 0) / n * 100

    if high_pct > 85:
        flags.append(f"WARNING: {high_pct:.0f}% flagged HIGH — model may over-predict pollution.")
    if low_pct > 85:
        flags.append(f"WARNING: {low_pct:.0f}% flagged LOW — model may under-predict.")
    if bad_pct > 90:
        flags.append(f"WARNING: EfficientNet says 'bad' on {bad_pct:.0f}% — possible over-confidence bias.")
    if not flags:
        flags.append("OK: Prediction distribution spans all classes — no obvious collapse.")

    for fl in flags:
        print(f"  {fl}")

    print()
    print("  NOTE: These are PREDICTIONS, not validated accuracy.")
    print("  The 'model_suggested_level' column can help annotators work faster,")
    print("  but they MUST label independently and can override any suggestion.")
    print("=" * 68)


if __name__ == "__main__":
    main()
