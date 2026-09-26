"""
Computer Vision Analysis Pipeline for Water Body Photos.

Combines seven analysis techniques:
1. Forel-Ule Colorimetric Analysis — dominant water color → FU index → quality score
2. Algae Detection — green-hue percentage in HSV space
3. Foam Detection — bright, low-saturation blob detection
4. Turbidity Estimation — Laplacian variance (edge sharpness)
5. Oil Sheen Detection — rainbow iridescence via high-saturation multi-hue patches
6. Color Abnormality — statistical distance from natural water color distribution
7. Surface Debris Detection — contour density analysis for floating objects
"""

import cv2
import numpy as np

from app.utils.forel_ule import (
    find_nearest_fu_index,
    get_fu_color_name,
    get_fu_quality_score,
)


def preprocess_image(image_bytes: bytes, max_dimension: int = 800) -> np.ndarray:
    """
    Decode image from bytes and prepare for analysis.

    - Decodes JPEG/PNG from raw bytes
    - Resizes if larger than max_dimension (maintains aspect ratio)
    - Extracts center 60% ROI (avoids edges/sky/banks)

    Args:
        image_bytes: Raw image file bytes.
        max_dimension: Maximum width or height in pixels.

    Returns:
        ROI as BGR numpy array.

    Raises:
        ValueError: If image cannot be decoded.
    """
    # Validate input
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("Image could not be decoded. Please upload a valid JPEG or PNG file.")

    # Decode from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    try:
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except cv2.error:
        raise ValueError("Image could not be decoded. Please upload a valid JPEG or PNG file.")

    if img is None:
        raise ValueError("Image could not be decoded. Please upload a valid JPEG or PNG file.")

    # Resize if too large (maintain aspect ratio)
    h, w = img.shape[:2]
    if max(h, w) > max_dimension:
        scale = max_dimension / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # Extract ROI: center 80% of image (wider to capture edge debris)
    h, w = img.shape[:2]
    y_start = int(h * 0.1)
    y_end = int(h * 0.9)
    x_start = int(w * 0.1)
    x_end = int(w * 0.9)
    roi = img[y_start:y_end, x_start:x_end]

    return roi


def analyze_forel_ule(roi: np.ndarray) -> dict:
    """
    Extract dominant water color and map to Forel-Ule index.

    Uses k-means clustering (k=3) to find the dominant color,
    then matches to the nearest FU reference color.

    Returns:
        {
            "fu_index": int (1-21),
            "fu_color_name": str,
            "fu_quality_score": float (0-100, higher = cleaner),
            "dominant_rgb": [r, g, b]
        }
    """
    # Convert BGR to RGB
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

    # Reshape to pixel list for k-means
    pixels = rgb.reshape(-1, 3).astype(np.float32)

    # K-means clustering (k=3) to find dominant colors
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = 3
    _, labels, centers = cv2.kmeans(
        pixels, k, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS
    )

    # Pick the largest cluster as dominant color
    counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(counts)
    dominant_color = centers[dominant_idx].astype(int)

    # Find nearest FU index
    dominant_rgb = tuple(dominant_color.tolist())
    fu_index = find_nearest_fu_index(dominant_rgb)

    return {
        "fu_index": fu_index,
        "fu_color_name": get_fu_color_name(fu_index),
        "fu_quality_score": get_fu_quality_score(fu_index),
        "dominant_rgb": list(dominant_rgb),
    }


def detect_algae(roi: np.ndarray) -> dict:
    """
    Detect green algae coverage using HSV color space.

    Green hues in OpenCV HSV: H=35-85, S>50, V>50.
    Calculates percentage of pixels in this range.

    Returns:
        {
            "algae_percentage": float (0-100),
            "severity": str ("none", "low", "moderate", "heavy")
        }
    """
    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Green hue range
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])

    # Create mask
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    # Calculate percentage
    total_pixels = roi.shape[0] * roi.shape[1]
    green_pixels = np.count_nonzero(green_mask)
    algae_percentage = (green_pixels / total_pixels) * 100

    # Classify severity
    if algae_percentage < 5:
        severity = "none"
    elif algae_percentage < 20:
        severity = "low"
    elif algae_percentage < 50:
        severity = "moderate"
    else:
        severity = "heavy"

    return {
        "algae_percentage": round(algae_percentage, 1),
        "severity": severity,
    }


def detect_foam(roi: np.ndarray) -> dict:
    """
    Detect foam/froth using HSV thresholding + contour analysis.

    Foam = bright (high V) + desaturated (low S).
    Filters small noise contours (< 500px area).

    Returns:
        {
            "foam_detected": bool,
            "foam_coverage_percentage": float (0-100),
            "foam_patch_count": int
        }
    """
    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Foam: low saturation + high value (bright white/off-white)
    lower_foam = np.array([0, 0, 200])
    upper_foam = np.array([179, 30, 255])

    foam_mask = cv2.inRange(hsv, lower_foam, upper_foam)

    # Morphological operations to clean noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    foam_mask = cv2.morphologyEx(foam_mask, cv2.MORPH_OPEN, kernel)
    foam_mask = cv2.morphologyEx(foam_mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(
        foam_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Filter small contours (noise) — minimum 500 pixels area
    min_area = 500
    valid_contours = [c for c in contours if cv2.contourArea(c) >= min_area]

    # Calculate coverage
    total_pixels = roi.shape[0] * roi.shape[1]
    foam_pixels = np.count_nonzero(foam_mask)
    foam_coverage = (foam_pixels / total_pixels) * 100

    return {
        "foam_detected": len(valid_contours) > 0,
        "foam_coverage_percentage": round(foam_coverage, 1),
        "foam_patch_count": len(valid_contours),
    }


def estimate_turbidity(roi: np.ndarray) -> dict:
    """
    Estimate water clarity using Laplacian variance.

    Higher Laplacian variance = more edges = could be clear OR debris-heavy.
    We combine with color uniformity to disambiguate:
    - High variance + uniform color = clear water with visible bottom
    - High variance + non-uniform color = debris/pollution

    Returns:
        {
            "turbidity_score": float (0-100, higher = clearer),
            "laplacian_variance": float (raw value),
            "clarity_description": str
        }
    """
    # Convert to grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Laplacian (second derivative — edge detection)
    laplacian = cv2.Laplacian(blurred, cv2.CV_64F)
    variance = float(laplacian.var())

    # Color standard deviation — high means patchy/non-uniform
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    color_std = float(np.std(s))  # Saturation variation
    brightness_std = float(np.std(v))  # Brightness variation

    # High edges + high color variation = debris, NOT clear water
    # Penalize clarity score when image has high variance AND non-uniform color
    max_variance = 300.0
    raw_clarity = min(100.0, (variance / max_variance) * 100)

    # If color is highly non-uniform (std > 40), reduce clarity score
    # because the "edges" are likely from debris, not visible bottom
    uniformity_penalty = 0.0
    if color_std > 40:
        uniformity_penalty = min(50.0, (color_std - 40) * 1.5)
    if brightness_std > 50:
        uniformity_penalty += min(30.0, (brightness_std - 50) * 1.0)

    # Dark water penalty — very dark images are likely polluted
    mean_brightness = float(np.mean(v))
    if mean_brightness < 100:
        uniformity_penalty += min(40.0, (100 - mean_brightness) * 0.8)

    # High edges + dark image = debris, not clarity
    if variance > 150 and mean_brightness < 130:
        uniformity_penalty += 25.0

    clarity_score = max(0.0, raw_clarity - uniformity_penalty)

    # Classify
    if clarity_score > 66:
        description = "Clear"
    elif clarity_score > 33:
        description = "Moderately Turbid"
    else:
        description = "Highly Turbid"

    return {
        "turbidity_score": round(clarity_score, 1),
        "laplacian_variance": round(variance, 2),
        "clarity_description": description,
    }


def detect_oil_sheen(roi: np.ndarray) -> dict:
    """
    Detect oil/chemical sheen (rainbow iridescence) on water surface.

    Oil sheens show up as patches with high saturation and rapidly varying hues
    (rainbow effect). We look for regions where hue variance is high within
    small local neighborhoods while saturation is also high.

    Returns:
        {
            "oil_sheen_detected": bool,
            "oil_coverage_percentage": float (0-100),
            "confidence": str ("none", "possible", "likely")
        }
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Oil sheen characteristics:
    # - High saturation (colorful, not grey)
    # - High local hue variance (multiple colors in small area = rainbow)
    # - Medium-high brightness

    # Step 1: Mask for saturated, bright regions (potential sheen)
    sat_mask = cv2.inRange(s, 80, 255)  # Reasonably saturated
    val_mask = cv2.inRange(v, 60, 240)  # Not too dark, not blown out
    candidate_mask = cv2.bitwise_and(sat_mask, val_mask)

    # Step 2: Calculate local hue variance using a sliding window
    # High hue variance in a small patch = rapid color change = iridescence
    h_float = h.astype(np.float32)
    kernel_size = 15
    h_mean = cv2.blur(h_float, (kernel_size, kernel_size))
    h_sq_mean = cv2.blur(h_float ** 2, (kernel_size, kernel_size))
    h_variance = h_sq_mean - h_mean ** 2
    h_variance = np.clip(h_variance, 0, None)

    # Threshold: high local hue variance indicates rainbow-like pattern
    # Normal water has uniform hue; oil sheen has rapid hue changes
    variance_threshold = 200.0
    high_variance_mask = (h_variance > variance_threshold).astype(np.uint8) * 255

    # Combine: must be both saturated AND have high hue variance
    rainbow_mask = cv2.bitwise_and(candidate_mask, high_variance_mask)

    # Clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    rainbow_mask = cv2.morphologyEx(rainbow_mask, cv2.MORPH_OPEN, kernel)

    # === Method 2: Thick oil slick detection (dark swirling patches) ===
    # Thick crude oil appears as dark, low-saturation, smooth patches that
    # contrast with surrounding water. Not rainbow — dark and opaque.
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Dark regions (oil slick is darker than surrounding water)
    mean_brightness = float(np.mean(gray))
    # Threshold: pixels significantly darker than the average
    dark_thresh = max(30, mean_brightness - 40)
    dark_mask = (gray < dark_thresh).astype(np.uint8) * 255

    # Oil slicks are smooth (low local texture) — filter out dark textured areas (vegetation, shadows)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    abs_lap = np.absolute(laplacian).astype(np.uint8)
    smooth_mask = (abs_lap < 15).astype(np.uint8) * 255

    # Low saturation (oil slick is not vividly colored)
    low_sat_mask = cv2.inRange(s, 0, 90)

    # Thick oil = dark AND smooth AND low saturation
    slick_mask = cv2.bitwise_and(dark_mask, smooth_mask)
    slick_mask = cv2.bitwise_and(slick_mask, low_sat_mask)

    # Clean up — remove small noise, keep sizable patches
    kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    slick_mask = cv2.morphologyEx(slick_mask, cv2.MORPH_OPEN, kernel2)
    slick_mask = cv2.morphologyEx(slick_mask, cv2.MORPH_CLOSE, kernel2)

    # Filter by contour size — oil slicks form large connected patches
    contours, _ = cv2.findContours(slick_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_pixels = roi.shape[0] * roi.shape[1]
    min_slick_area = total_pixels * 0.01  # At least 1% of image in one patch
    valid_slick = np.zeros_like(slick_mask)
    for c in contours:
        if cv2.contourArea(c) >= min_slick_area:
            cv2.drawContours(valid_slick, [c], -1, 255, -1)

    # Combine both detection methods
    oil_mask = cv2.bitwise_or(rainbow_mask, valid_slick)

    # Calculate coverage
    oil_pixels = np.count_nonzero(oil_mask)
    oil_coverage = (oil_pixels / total_pixels) * 100

    rainbow_pixels = np.count_nonzero(rainbow_mask)
    slick_pixels = np.count_nonzero(valid_slick)
    rainbow_pct = (rainbow_pixels / total_pixels) * 100
    slick_pct = (slick_pixels / total_pixels) * 100

    # Determine oil type
    if slick_pct > rainbow_pct and slick_pct > 2:
        oil_type = "thick slick"
    elif rainbow_pct > 1:
        oil_type = "rainbow sheen"
    else:
        oil_type = "none"

    # Classify confidence
    if oil_coverage < 1.0:
        confidence = "none"
    elif oil_coverage < 5.0:
        confidence = "possible"
    else:
        confidence = "likely"

    return {
        "oil_sheen_detected": oil_coverage >= 1.0,
        "oil_coverage_percentage": round(oil_coverage, 1),
        "confidence": confidence,
        "oil_type": oil_type,
    }


def analyze_color_abnormality(roi: np.ndarray) -> dict:
    """
    Measure how abnormal the water color distribution is.

    Natural water tends to have a narrow color distribution (blues, greens, browns).
    Polluted water often has unnatural colors (purple, bright orange, grey)
    or high color variance (patchy, multi-colored surface).

    Uses:
    - Standard deviation across color channels (high = unnatural variation)
    - Presence of "unnatural" hues (purple, magenta, bright red in water)

    Returns:
        {
            "color_abnormality_score": float (0-100, higher = more abnormal),
            "color_uniformity": float (0-100, higher = more uniform),
            "unnatural_color_percentage": float (0-100),
            "description": str
        }
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # 1. Color uniformity: standard deviation of hue (in saturated pixels only)
    # Saturated pixels only (avoid counting grey/white/black)
    saturated_mask = s > 40
    if np.count_nonzero(saturated_mask) > 100:
        hue_std = float(np.std(h[saturated_mask]))
    else:
        hue_std = 0.0

    # Normalize hue std: 0-90 range typically (0=uniform, 90=wildly varied)
    # OpenCV hue is 0-179
    max_std = 60.0
    color_uniformity = max(0.0, 100.0 - (hue_std / max_std) * 100.0)

    # 2. Unnatural colors: purple/magenta (H=125-165), bright red (H=0-10 with high S)
    # These almost never appear naturally in water
    purple_mask = cv2.inRange(hsv, np.array([125, 50, 50]), np.array([165, 255, 255]))
    bright_red_mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
    unnatural_mask = cv2.bitwise_or(purple_mask, bright_red_mask)

    total_pixels = roi.shape[0] * roi.shape[1]
    unnatural_pct = (np.count_nonzero(unnatural_mask) / total_pixels) * 100

    # 3. Overall abnormality score
    # Combine: non-uniform + unnatural colors
    abnormality = ((100.0 - color_uniformity) * 0.6) + (min(unnatural_pct * 5, 100) * 0.4)
    abnormality = max(0.0, min(100.0, abnormality))

    # Classify
    if abnormality < 20:
        description = "Normal"
    elif abnormality < 50:
        description = "Slightly Abnormal"
    else:
        description = "Highly Abnormal"

    return {
        "color_abnormality_score": round(abnormality, 1),
        "color_uniformity": round(color_uniformity, 1),
        "unnatural_color_percentage": round(unnatural_pct, 1),
        "description": description,
    }


def detect_surface_debris(roi: np.ndarray) -> dict:
    """
    Detect floating surface debris/solid waste via contour density analysis.

    Solid waste on water creates many small, high-contrast contours against
    the water background. Clean water has very few distinct contours.

    Uses Canny edge detection + contour counting normalized by image area.

    Returns:
        {
            "debris_detected": bool,
            "contour_density": float (0-100, higher = more debris),
            "significant_objects": int (number of large contours),
            "description": str
        }
    """
    # Convert to grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Bilateral filter: smooths while preserving edges (better than Gaussian for debris)
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)

    # Adaptive thresholding to find objects distinct from water background
    thresh = cv2.adaptiveThreshold(
        filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological operations to remove noise, keep actual objects
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by size
    total_pixels = roi.shape[0] * roi.shape[1]
    min_area = total_pixels * 0.0005  # At least 0.05% of image (lowered for small debris)
    max_area = total_pixels * 0.3     # No more than 30% (too large = not debris)

    significant_contours = [
        c for c in contours
        if min_area <= cv2.contourArea(c) <= max_area
    ]

    # Contour density: area covered by significant contours / total area
    debris_area = sum(cv2.contourArea(c) for c in significant_contours)
    contour_density = (debris_area / total_pixels) * 100

    # Normalize to 0-100 (cap at 30% coverage = 100 score)
    density_score = min(100.0, (contour_density / 30.0) * 100.0)

    # Classify
    if density_score < 10:
        description = "Clean Surface"
    elif density_score < 30:
        description = "Some Debris"
    elif density_score < 60:
        description = "Moderate Debris"
    else:
        description = "Heavy Debris"

    return {
        "debris_detected": density_score >= 10,
        "contour_density": round(density_score, 1),
        "significant_objects": len(significant_contours),
        "description": description,
    }


def analyze_image(image_bytes: bytes) -> dict:
    """
    Run the full CV analysis pipeline on an image.

    This is the main entry point — call this from the API endpoint.

    Runs 7 analyses:
    1. Forel-Ule colorimetry
    2. Algae detection
    3. Foam detection
    4. Turbidity estimation
    5. Oil sheen detection
    6. Color abnormality
    7. Surface debris detection

    Args:
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        Complete analysis results dictionary with all components.

    Raises:
        ValueError: If image cannot be decoded.
    """
    # Pre-process
    roi = preprocess_image(image_bytes)

    # Run all analyses
    fu_result = analyze_forel_ule(roi)
    algae_result = detect_algae(roi)
    foam_result = detect_foam(roi)
    turbidity_result = estimate_turbidity(roi)
    oil_result = detect_oil_sheen(roi)
    color_result = analyze_color_abnormality(roi)
    debris_result = detect_surface_debris(roi)

    results = {
        "forel_ule": fu_result,
        "algae": algae_result,
        "foam": foam_result,
        "turbidity": turbidity_result,
        "oil_sheen": oil_result,
        "color_abnormality": color_result,
        "surface_debris": debris_result,
    }

    # Convert all numpy types to plain Python types for JSON serialization
    return _convert_numpy(results)


def _convert_numpy(obj):
    """Recursively convert numpy types to Python native types."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy(i) for i in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj
