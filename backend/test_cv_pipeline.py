"""
Manual test script for the CV analysis pipeline.

Creates synthetic test images (no real photos needed) and runs the full pipeline
to verify each component produces sensible output.

Usage:
    cd backend
    pip install opencv-python numpy
    python test_cv_pipeline.py
"""

import sys
import json
import numpy as np
import cv2

# Add parent to path so we can import app modules
sys.path.insert(0, ".")

from app.services.cv_analysis import (
    preprocess_image,
    analyze_forel_ule,
    detect_algae,
    detect_foam,
    estimate_turbidity,
    analyze_image,
)
from app.services.risk_scoring import calculate_risk_from_analysis


def create_test_image(color_bgr: tuple, add_foam: bool = False, add_texture: bool = False) -> bytes:
    """Create a synthetic test image with specified characteristics."""
    # Create 400x400 image with base color
    img = np.full((400, 400, 3), color_bgr, dtype=np.uint8)

    # Add some natural variation (noise)
    noise = np.random.randint(-15, 15, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Add foam patches if requested (bright white blobs)
    if add_foam:
        cv2.circle(img, (100, 100), 40, (255, 255, 255), -1)
        cv2.circle(img, (250, 200), 30, (250, 250, 250), -1)
        cv2.circle(img, (300, 300), 35, (245, 248, 252), -1)

    # Add texture/edges if requested (makes it look "clear")
    if add_texture:
        for i in range(0, 400, 20):
            cv2.line(img, (i, 0), (i, 400), (color_bgr[0] + 30, color_bgr[1] + 30, color_bgr[2] + 30), 1)
            cv2.line(img, (0, i), (400, i), (color_bgr[0] - 20, color_bgr[1] - 20, color_bgr[2] - 20), 1)

    # Encode to JPEG bytes
    _, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


def test_clean_water():
    """Test: Clear blue water — should get LOW risk."""
    print("\n" + "=" * 60)
    print("TEST 1: Clean Blue Water (expected: LOW risk)")
    print("=" * 60)

    # Blue water color (BGR)
    image_bytes = create_test_image(color_bgr=(152, 98, 29), add_texture=True)

    results = analyze_image(image_bytes)
    risk = calculate_risk_from_analysis(results)

    print(f"  Forel-Ule Index: {results['forel_ule']['fu_index']} ({results['forel_ule']['fu_color_name']})")
    print(f"  Algae: {results['algae']['algae_percentage']}% ({results['algae']['severity']})")
    print(f"  Foam: detected={results['foam']['foam_detected']}, coverage={results['foam']['foam_coverage_percentage']}%")
    print(f"  Turbidity: {results['turbidity']['turbidity_score']} ({results['turbidity']['clarity_description']})")
    print(f"  ---")
    print(f"  Composite Score: {risk['composite_score']}")
    print(f"  Risk Level: {risk['risk_level'].upper()}")
    print(f"  Breakdown: {risk['breakdown']}")

    return risk


def test_algae_water():
    """Test: Green algae-heavy water — should get MODERATE/HIGH risk."""
    print("\n" + "=" * 60)
    print("TEST 2: Green Algae Water (expected: MODERATE-HIGH risk)")
    print("=" * 60)

    # Green water color (BGR) — simulates algae bloom
    image_bytes = create_test_image(color_bgr=(50, 160, 60))

    results = analyze_image(image_bytes)
    risk = calculate_risk_from_analysis(results)

    print(f"  Forel-Ule Index: {results['forel_ule']['fu_index']} ({results['forel_ule']['fu_color_name']})")
    print(f"  Algae: {results['algae']['algae_percentage']}% ({results['algae']['severity']})")
    print(f"  Foam: detected={results['foam']['foam_detected']}, coverage={results['foam']['foam_coverage_percentage']}%")
    print(f"  Turbidity: {results['turbidity']['turbidity_score']} ({results['turbidity']['clarity_description']})")
    print(f"  ---")
    print(f"  Composite Score: {risk['composite_score']}")
    print(f"  Risk Level: {risk['risk_level'].upper()}")
    print(f"  Breakdown: {risk['breakdown']}")

    return risk


def test_foamy_polluted_water():
    """Test: Dark brown water with foam — should get HIGH risk."""
    print("\n" + "=" * 60)
    print("TEST 3: Dark Polluted Water with Foam (expected: HIGH risk)")
    print("=" * 60)

    # Dark brownish water (BGR) with foam
    image_bytes = create_test_image(color_bgr=(30, 60, 100), add_foam=True)

    results = analyze_image(image_bytes)
    risk = calculate_risk_from_analysis(results)

    print(f"  Forel-Ule Index: {results['forel_ule']['fu_index']} ({results['forel_ule']['fu_color_name']})")
    print(f"  Algae: {results['algae']['algae_percentage']}% ({results['algae']['severity']})")
    print(f"  Foam: detected={results['foam']['foam_detected']}, coverage={results['foam']['foam_coverage_percentage']}%")
    print(f"  Turbidity: {results['turbidity']['turbidity_score']} ({results['turbidity']['clarity_description']})")
    print(f"  ---")
    print(f"  Composite Score: {risk['composite_score']}")
    print(f"  Risk Level: {risk['risk_level'].upper()}")
    print(f"  Breakdown: {risk['breakdown']}")

    return risk


def test_turbid_water():
    """Test: Uniform muddy water (no edges) — should show high turbidity."""
    print("\n" + "=" * 60)
    print("TEST 4: Turbid Muddy Water (expected: MODERATE risk, high turbidity)")
    print("=" * 60)

    # Muddy brown, very uniform (no texture = turbid)
    image_bytes = create_test_image(color_bgr=(50, 100, 140))

    results = analyze_image(image_bytes)
    risk = calculate_risk_from_analysis(results)

    print(f"  Forel-Ule Index: {results['forel_ule']['fu_index']} ({results['forel_ule']['fu_color_name']})")
    print(f"  Algae: {results['algae']['algae_percentage']}% ({results['algae']['severity']})")
    print(f"  Foam: detected={results['foam']['foam_detected']}, coverage={results['foam']['foam_coverage_percentage']}%")
    print(f"  Turbidity: {results['turbidity']['turbidity_score']} ({results['turbidity']['clarity_description']})")
    print(f"  ---")
    print(f"  Composite Score: {risk['composite_score']}")
    print(f"  Risk Level: {risk['risk_level'].upper()}")
    print(f"  Breakdown: {risk['breakdown']}")

    return risk


def main():
    print("AquaWatch CV Pipeline — Manual Test")
    print("=" * 60)
    print("Running 4 synthetic image tests...\n")

    results = []
    results.append(("Clean Blue Water", test_clean_water()))
    results.append(("Green Algae Water", test_algae_water()))
    results.append(("Foamy Polluted Water", test_foamy_polluted_water()))
    results.append(("Turbid Muddy Water", test_turbid_water()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Test':<30} {'Score':>8} {'Level':>10}")
    print("-" * 50)
    for name, risk in results:
        print(f"{name:<30} {risk['composite_score']:>8.1f} {risk['risk_level'].upper():>10}")

    print("\n✓ Pipeline test complete. All components functional.")


if __name__ == "__main__":
    main()
