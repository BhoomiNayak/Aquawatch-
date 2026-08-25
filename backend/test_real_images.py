"""
Test CV pipeline on real water body photos.

Usage:
    1. Add images to backend/test_images/ (jpg or png)
    2. Run: python test_real_images.py

It will analyze every image in the folder and print results.
"""

import os
import sys
import glob

sys.path.insert(0, ".")

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis


def analyze_file(filepath: str) -> None:
    """Run full pipeline on a single image file."""
    filename = os.path.basename(filepath)
    print(f"\n{'=' * 60}")
    print(f"  FILE: {filename}")
    print(f"{'=' * 60}")

    # Read file bytes
    with open(filepath, "rb") as f:
        image_bytes = f.read()

    file_size_kb = len(image_bytes) / 1024
    print(f"  Size: {file_size_kb:.1f} KB")

    try:
        # Run CV analysis
        results = analyze_image(image_bytes)
        risk = calculate_risk_from_analysis(results)

        # Print results
        print(f"\n  --- Forel-Ule Colorimetry ---")
        print(f"  FU Index: {results['forel_ule']['fu_index']} ({results['forel_ule']['fu_color_name']})")
        print(f"  FU Quality: {results['forel_ule']['fu_quality_score']}/100")
        print(f"  Dominant Color (RGB): {results['forel_ule']['dominant_rgb']}")

        print(f"\n  --- Algae Detection ---")
        print(f"  Algae: {results['algae']['algae_percentage']}% — {results['algae']['severity']}")

        print(f"\n  --- Foam Detection ---")
        print(f"  Foam: detected={results['foam']['foam_detected']}, coverage={results['foam']['foam_coverage_percentage']}%, patches={results['foam']['foam_patch_count']}")

        print(f"\n  --- Turbidity ---")
        print(f"  Clarity: {results['turbidity']['turbidity_score']}/100 — {results['turbidity']['clarity_description']}")
        print(f"  Laplacian variance: {results['turbidity']['laplacian_variance']}")

        print(f"\n  --- Oil Sheen ---")
        print(f"  Oil: detected={results['oil_sheen']['oil_sheen_detected']}, coverage={results['oil_sheen']['oil_coverage_percentage']}%, confidence={results['oil_sheen']['confidence']}")

        print(f"\n  --- Color Abnormality ---")
        print(f"  Abnormality: {results['color_abnormality']['color_abnormality_score']}/100 — {results['color_abnormality']['description']}")
        print(f"  Uniformity: {results['color_abnormality']['color_uniformity']}/100")
        print(f"  Unnatural colors: {results['color_abnormality']['unnatural_color_percentage']}%")

        print(f"\n  --- Surface Debris ---")
        print(f"  Debris: detected={results['surface_debris']['debris_detected']}, density={results['surface_debris']['contour_density']}/100")
        print(f"  Objects: {results['surface_debris']['significant_objects']} — {results['surface_debris']['description']}")

        print(f"\n  {'─' * 40}")
        print(f"  ┌─────────────────────────────────────┐")
        print(f"  │  COMPOSITE SCORE: {risk['composite_score']:>6.1f} / 100     │")
        print(f"  │  RISK LEVEL:      {risk['risk_level'].upper():<18}│")
        print(f"  └─────────────────────────────────────┘")
        print(f"  Breakdown:")
        for component, value in risk['breakdown'].items():
            bar_len = int(value / 2)
            bar = '█' * bar_len
            print(f"    {component:<30} {value:>5.2f}  {bar}")

    except ValueError as e:
        print(f"  ERROR: {e}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


def main():
    image_dir = os.path.join(os.path.dirname(__file__), "test_images")

    # Find all images
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(image_dir, ext)))

    if not image_files:
        print("No images found in backend/test_images/")
        print("Add some water body photos (.jpg, .png) and run again.")
        return

    print(f"AquaWatch CV Pipeline — Real Image Test (7-Factor Analysis)")
    print(f"Found {len(image_files)} image(s) in test_images/")

    for filepath in sorted(image_files):
        analyze_file(filepath)

    print(f"\n{'=' * 60}")
    print(f"Done. Analyzed {len(image_files)} image(s).")


if __name__ == "__main__":
    main()
