"""
Threshold Calibration Script.

Runs the 7-factor CV pipeline on all polluted water images in the dataset,
analyzes the score distribution, and recommends threshold adjustments.

Goal: These are ALL polluted images — they should score MODERATE or HIGH.
If many score LOW, our thresholds/weights need tuning.

Usage:
    cd backend
    python calibrate_thresholds.py
"""

import os
import sys
import glob
import time
import numpy as np

sys.path.insert(0, ".")

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis


def main():
    dataset_dir = os.path.join(os.path.dirname(__file__), "waterpollution")

    # Find all images
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG")
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(dataset_dir, ext)))

    print(f"AquaWatch — Threshold Calibration")
    print(f"Dataset: {len(image_files)} polluted water images")
    print(f"Expected: All should score MODERATE or HIGH")
    print(f"{'=' * 60}\n")

    # Storage for results
    scores = []
    risk_levels = {"low": 0, "moderate": 0, "high": 0}
    feature_sums = {
        "algae_percentage": [],
        "foam_coverage": [],
        "turbidity_score": [],
        "fu_quality_score": [],
        "oil_coverage": [],
        "color_abnormality": [],
        "debris_density": [],
    }
    errors = 0

    start_time = time.time()

    for i, filepath in enumerate(sorted(image_files)):
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            print(f"  Processing {i + 1}/{len(image_files)}... ({elapsed:.1f}s elapsed)")

        try:
            with open(filepath, "rb") as f:
                image_bytes = f.read()

            results = analyze_image(image_bytes)
            risk = calculate_risk_from_analysis(results)

            scores.append(risk["composite_score"])
            risk_levels[risk["risk_level"]] += 1

            # Collect feature values
            feature_sums["algae_percentage"].append(results["algae"]["algae_percentage"])
            feature_sums["foam_coverage"].append(results["foam"]["foam_coverage_percentage"])
            feature_sums["turbidity_score"].append(results["turbidity"]["turbidity_score"])
            feature_sums["fu_quality_score"].append(results["forel_ule"]["fu_quality_score"])
            feature_sums["oil_coverage"].append(results["oil_sheen"]["oil_coverage_percentage"])
            feature_sums["color_abnormality"].append(results["color_abnormality"]["color_abnormality_score"])
            feature_sums["debris_density"].append(results["surface_debris"]["contour_density"])

        except Exception as e:
            errors += 1

    elapsed = time.time() - start_time
    total_valid = len(scores)

    print(f"\n{'=' * 60}")
    print(f"RESULTS ({total_valid} images analyzed in {elapsed:.1f}s, {errors} errors)")
    print(f"{'=' * 60}\n")

    # Score distribution
    scores_arr = np.array(scores)
    print(f"--- SCORE DISTRIBUTION ---")
    print(f"  Min:    {scores_arr.min():.1f}")
    print(f"  Max:    {scores_arr.max():.1f}")
    print(f"  Mean:   {scores_arr.mean():.1f}")
    print(f"  Median: {np.median(scores_arr):.1f}")
    print(f"  Std:    {scores_arr.std():.1f}")
    print()

    # Percentiles
    print(f"--- PERCENTILES ---")
    for p in [10, 25, 50, 75, 90]:
        print(f"  P{p}: {np.percentile(scores_arr, p):.1f}")
    print()

    # Risk level distribution
    print(f"--- RISK LEVEL COUNTS ---")
    for level, count in risk_levels.items():
        pct = (count / total_valid) * 100
        bar = "█" * int(pct / 2)
        print(f"  {level.upper():<10} {count:>4} ({pct:>5.1f}%) {bar}")
    print()

    # Feature statistics
    print(f"--- FEATURE STATISTICS (across all polluted images) ---")
    print(f"  {'Feature':<25} {'Mean':>8} {'Median':>8} {'Std':>8} {'Max':>8}")
    print(f"  {'-' * 60}")
    for feature, values in feature_sums.items():
        arr = np.array(values)
        print(f"  {feature:<25} {arr.mean():>8.1f} {np.median(arr):>8.1f} {arr.std():>8.1f} {arr.max():>8.1f}")
    print()

    # Analysis
    low_pct = (risk_levels["low"] / total_valid) * 100
    print(f"--- CALIBRATION ANALYSIS ---")
    print(f"  Images classified as LOW (should be 0%): {risk_levels['low']} ({low_pct:.1f}%)")
    print()

    if low_pct > 20:
        print(f"  ⚠️  {low_pct:.0f}% of POLLUTED images are scoring LOW — thresholds need adjustment.")
        print()
        print(f"  RECOMMENDATIONS:")
        print(f"  1. Lower the LOW/MODERATE threshold from 33 to {np.percentile(scores_arr, 15):.0f}")
        print(f"  2. OR increase weights for factors that detect pollution in these images")
        print()

        # Identify which features are contributing most
        print(f"  TOP CONTRIBUTING FEATURES (by mean value in this dataset):")
        sorted_features = sorted(feature_sums.items(), key=lambda x: np.mean(x[1]), reverse=True)
        for feat, vals in sorted_features[:4]:
            print(f"    {feat}: mean={np.mean(vals):.1f}")
    else:
        print(f"  ✓ Good calibration — only {low_pct:.0f}% false negatives on polluted images.")

    # Suggested new thresholds
    print(f"\n--- SUGGESTED THRESHOLDS ---")
    p20 = np.percentile(scores_arr, 20)
    p50 = np.percentile(scores_arr, 50)
    print(f"  Current:   LOW < 33 | MODERATE 33-66 | HIGH > 66")
    print(f"  Suggested: LOW < {p20:.0f} | MODERATE {p20:.0f}-{p50 + 15:.0f} | HIGH > {p50 + 15:.0f}")
    print(f"  (Based on: P20={p20:.1f}, median={np.median(scores_arr):.1f})")


if __name__ == "__main__":
    main()
