"""
Risk Scoring Service.

Calculates a composite pollution risk score (0-100) from 7 CV analysis components.

Weights calibrated against 565 real-world polluted water images.
Thresholds set so polluted images reliably score MODERATE or HIGH.

Formula (weighted sum):
    score = (algae × 0.20)
          + (foam × 0.15)
          + ((100 - clarity) × 0.15)
          + ((100 - fu_quality) × 0.10)
          + (oil_sheen × 0.10)
          + (color_abnormality × 0.18)
          + (debris × 0.12)

Risk Levels (calibrated):
    LOW:      0 - 15
    MODERATE: 16 - 35
    HIGH:     36 - 100
"""


# Component weights (sum = 1.0)
# Calibrated: debris and turbidity are critical for solid waste pollution
WEIGHTS = {
    "algae": 0.15,
    "foam": 0.18,
    "turbidity": 0.18,           # Inverted: low clarity = high contribution
    "forel_ule": 0.10,           # Inverted: low FU quality = high contribution
    "oil_sheen": 0.07,
    "color_abnormality": 0.15,   # Unnatural colors
    "debris": 0.17,              # Floating waste is strongest visual indicator
}

# Thresholds (calibrated from 565 polluted images)
# Polluted images: median score ~18, P75 ~23, P90 ~28
# These thresholds ensure polluted water gets flagged appropriately
THRESHOLD_LOW = 15.0
THRESHOLD_MODERATE = 35.0


def calculate_composite_score(
    algae_percentage: float,
    foam_coverage_percentage: float,
    turbidity_score: float,
    fu_quality_score: float,
    oil_coverage_percentage: float = 0.0,
    color_abnormality_score: float = 0.0,
    debris_density: float = 0.0,
) -> dict:
    """
    Calculate the composite risk score from all CV analysis outputs.

    Args:
        algae_percentage: 0-100 (higher = more algae)
        foam_coverage_percentage: 0-100 (higher = more foam)
        turbidity_score: 0-100 (higher = CLEARER, so we invert)
        fu_quality_score: 0-100 (higher = CLEANER water, so we invert)
        oil_coverage_percentage: 0-100 (higher = more oil sheen)
        color_abnormality_score: 0-100 (higher = more abnormal)
        debris_density: 0-100 (higher = more debris)

    Returns:
        {
            "composite_score": float (0-100),
            "risk_level": str ("low", "moderate", "high"),
            "breakdown": { ... per-component contributions }
        }
    """
    # Clamp all inputs to 0-100
    algae_percentage = _clamp(algae_percentage)
    foam_coverage_percentage = _clamp(foam_coverage_percentage)
    turbidity_score = _clamp(turbidity_score)
    fu_quality_score = _clamp(fu_quality_score)
    oil_coverage_percentage = _clamp(oil_coverage_percentage)
    color_abnormality_score = _clamp(color_abnormality_score)
    debris_density = _clamp(debris_density)

    # Calculate weighted components
    # Direct factors (higher input = higher risk contribution)
    algae_component = algae_percentage * WEIGHTS["algae"]
    foam_component = foam_coverage_percentage * WEIGHTS["foam"]
    oil_component = oil_coverage_percentage * WEIGHTS["oil_sheen"]
    color_component = color_abnormality_score * WEIGHTS["color_abnormality"]
    debris_component = debris_density * WEIGHTS["debris"]

    # Inverted factors (higher input = LOWER risk, so we invert)
    turbidity_component = (100.0 - turbidity_score) * WEIGHTS["turbidity"]
    fu_component = (100.0 - fu_quality_score) * WEIGHTS["forel_ule"]

    # Sum
    composite = (
        algae_component
        + foam_component
        + turbidity_component
        + fu_component
        + oil_component
        + color_component
        + debris_component
    )
    composite = _clamp(composite)

    # Classify
    risk_level = classify_risk_level(composite)

    return {
        "composite_score": round(composite, 1),
        "risk_level": risk_level,
        "breakdown": {
            "algae_component": round(float(algae_component), 2),
            "foam_component": round(float(foam_component), 2),
            "turbidity_component": round(float(turbidity_component), 2),
            "forel_ule_component": round(float(fu_component), 2),
            "oil_sheen_component": round(float(oil_component), 2),
            "color_abnormality_component": round(float(color_component), 2),
            "debris_component": round(float(debris_component), 2),
        },
    }


def classify_risk_level(score: float) -> str:
    """
    Classify a composite score into low/moderate/high.

    Thresholds calibrated from real polluted water images:
    - LOW:      0 - 15   (clean/near-clean water)
    - MODERATE: 16 - 35  (some pollution indicators)
    - HIGH:     36 - 100 (significant pollution)
    """
    if score <= THRESHOLD_LOW:
        return "low"
    elif score <= THRESHOLD_MODERATE:
        return "moderate"
    else:
        return "high"


def calculate_risk_from_analysis(analysis_results: dict) -> dict:
    """
    Convenience function: takes full CV analysis output and returns risk score.

    This is the function called from the API endpoint after analyze_image().

    Args:
        analysis_results: Output from cv_analysis.analyze_image()

    Returns:
        Same as calculate_composite_score()
    """
    return calculate_composite_score(
        algae_percentage=analysis_results["algae"]["algae_percentage"],
        foam_coverage_percentage=analysis_results["foam"]["foam_coverage_percentage"],
        turbidity_score=analysis_results["turbidity"]["turbidity_score"],
        fu_quality_score=analysis_results["forel_ule"]["fu_quality_score"],
        oil_coverage_percentage=analysis_results["oil_sheen"]["oil_coverage_percentage"],
        color_abnormality_score=analysis_results["color_abnormality"]["color_abnormality_score"],
        debris_density=analysis_results["surface_debris"]["contour_density"],
    )


def _clamp(value: float) -> float:
    """Clamp a value to 0-100 range."""
    return max(0.0, min(100.0, float(value)))
