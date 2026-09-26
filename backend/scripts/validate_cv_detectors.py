"""
validate_cv_detectors.py
========================
Label-free validation of the CV pipeline's individual detectors against
the pollution-TYPE dataset (clean_water_pollution_dataset).

Question answered:
  "Does each CV heuristic fire on the pollution type it's supposed to detect?"

  e.g. does the oil-sheen detector light up on the oily_chemical folder?
       does algae detection fire on algal_foam?
       does debris/contour density fire on garbage/plastic?

This is NOT accuracy (no severity labels). It's DETECTOR VALIDATION —
checks whether our hand-built CV features respond to the right stimuli.
Useful for the paper's "explainability / feature validation" section.

USAGE:
    cd backend
    python scripts/validate_cv_detectors.py

OUTPUTS:
    reports/cv_detector_validation.json
    reports/cv_detector_validation.txt   (paper-ready table)
"""

import os
import sys
import glob
import json
import logging
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

import numpy as np
from app.services.cv_analysis import analyze_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("cv_validate")

DATA_DIR = os.path.join(BASE, "datasets", "IndianWaterDataset",
                        "clean_water_pollution_dataset")
OUT_JSON = os.path.join(BASE, "reports", "cv_detector_validation.json")
OUT_TXT  = os.path.join(BASE, "reports", "cv_detector_validation.txt")

# Which CV detector SHOULD fire strongest for each pollution-type folder.
# This is the hypothesis we're validating.
EXPECTED_DETECTOR = {
    "algal_foam":      ["algae", "foam"],
    "garbage":         ["debris"],
    "plastic":         ["debris"],
    "oily_chemical":   ["oil"],
    "sewage":          ["color_abnormality", "turbidity"],
    "polluted_lakes":  ["algae", "color_abnormality"],
    "polluted_rivers": ["turbidity", "color_abnormality"],
    "marine":          ["color_abnormality"],
}


def extract_features(cv):
    """Pull the comparable 0-100 signal from each detector."""
    return {
        "algae":             float(cv["algae"]["algae_percentage"]),
        "foam":              float(cv["foam"]["foam_coverage_percentage"]),
        "turbidity":         float(100 - cv["turbidity"]["turbidity_score"]),  # invert: high=turbid
        "oil":               float(cv["oil_sheen"]["oil_coverage_percentage"]),
        "color_abnormality": float(cv["color_abnormality"]["color_abnormality_score"]),
        "debris":            float(cv["surface_debris"]["contour_density"]),
        "fu_index":          float(cv["forel_ule"]["fu_index"]),
    }


def main():
    print("=" * 74)
    print("AquaWatch — CV Detector Validation (label-free, pollution-type)")
    print("=" * 74)

    folders = [d for d in EXPECTED_DETECTOR.keys()
               if os.path.isdir(os.path.join(DATA_DIR, d))]
    if not folders:
        print(f"  No category folders found in {DATA_DIR}")
        return

    # per-folder mean of each detector
    folder_means = {}
    folder_counts = {}
    all_feature_names = ["algae", "foam", "turbidity", "oil",
                         "color_abnormality", "debris"]

    for folder in folders:
        paths = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            paths.extend(glob.glob(os.path.join(DATA_DIR, folder, ext)))
        feats = defaultdict(list)
        errors = 0
        for p in paths:
            try:
                with open(p, "rb") as fh:
                    cv = analyze_image(fh.read())
                f = extract_features(cv)
                for k, v in f.items():
                    feats[k].append(v)
            except Exception as e:
                errors += 1
        means = {k: round(float(np.mean(v)), 1) for k, v in feats.items() if v}
        folder_means[folder] = means
        folder_counts[folder] = len(paths) - errors
        log.info(f"  {folder}: {folder_counts[folder]} images processed")

    # ── Build the detector-response matrix ─────────────────────────
    # For each detector, compute its mean per folder, then z-score across
    # folders so we can see WHERE each detector responds most strongly.
    matrix = {feat: {f: folder_means[f].get(feat, 0.0) for f in folders}
              for feat in all_feature_names}

    # Validation check: does the expected detector rank in the top-2
    # strongest folders for its category?
    validation = {}
    for folder in folders:
        expected = EXPECTED_DETECTOR[folder]
        # rank this folder's detectors by strength
        dets = folder_means[folder]
        ranked = sorted([(k, v) for k, v in dets.items()
                         if k in all_feature_names],
                        key=lambda x: x[1], reverse=True)
        top2 = [k for k, _ in ranked[:2]]
        hit = any(e in top2 for e in expected)
        validation[folder] = {
            "expected_detectors": expected,
            "top2_actual": top2,
            "match": hit,
            "detector_values": {k: v for k, v in ranked},
        }

    n_match = sum(1 for v in validation.values() if v["match"])

    report = {
        "dataset": DATA_DIR,
        "folders_tested": folders,
        "image_counts": folder_counts,
        "detector_means_per_folder": folder_means,
        "validation": validation,
        "detectors_matched": n_match,
        "total_categories": len(folders),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(report, f, indent=2)

    # ── Paper-ready table ──────────────────────────────────────────
    lines = []
    lines.append("=" * 90)
    lines.append("CV DETECTOR RESPONSE MATRIX  (mean detector value per pollution-type folder)")
    lines.append("=" * 90)
    header = f"{'Category':<17}" + "".join(f"{d[:9]:>11}" for d in all_feature_names)
    lines.append(header)
    lines.append("-" * 90)
    for folder in folders:
        row = f"{folder:<17}"
        for feat in all_feature_names:
            val = folder_means[folder].get(feat, 0.0)
            row += f"{val:>11.1f}"
        lines.append(row)
    lines.append("")
    lines.append("=" * 90)
    lines.append("DETECTOR VALIDATION  (does the right detector fire for each category?)")
    lines.append("=" * 90)
    lines.append(f"{'Category':<17}{'Expected':<28}{'Top-2 Actual':<28}{'Match':>6}")
    lines.append("-" * 90)
    for folder in folders:
        v = validation[folder]
        exp = "+".join(v["expected_detectors"])
        act = "+".join(v["top2_actual"])
        mark = "YES" if v["match"] else "no"
        lines.append(f"{folder:<17}{exp:<28}{act:<28}{mark:>6}")
    lines.append("-" * 90)
    lines.append(f"Detectors firing correctly: {n_match}/{len(folders)} categories "
                 f"({n_match/len(folders)*100:.0f}%)")
    lines.append("=" * 90)

    table = "\n".join(lines)
    with open(OUT_TXT, "w") as f:
        f.write(table)

    print("\n" + table)
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")

    # ── Interpretation ─────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("INTERPRETATION")
    print("=" * 74)
    print(f"  {n_match}/{len(folders)} pollution categories had the EXPECTED detector")
    print(f"  fire in their top-2 strongest signals.")
    print()
    if n_match >= len(folders) * 0.6:
        print("  RESULT: CV detectors are largely responding to the correct stimuli.")
        print("  This supports the explainability claim — the heuristics measure")
        print("  what they're designed to measure.")
    else:
        print("  RESULT: Several detectors do NOT fire on their expected category.")
        print("  This flags which CV heuristics need re-tuning or re-thinking.")
    print("=" * 74)


if __name__ == "__main__":
    main()
