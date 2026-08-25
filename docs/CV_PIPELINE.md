# AquaWatch - Computer Vision Pipeline

## Overview

AquaWatch uses **classical computer vision** (no ML, no training data) to analyze water body photos. The pipeline combines three scientifically grounded techniques to produce a composite pollution risk score.

---

## Pipeline Architecture

```
Input Image (JPEG/PNG)
       │
       ▼
┌──────────────────┐
│  Pre-processing  │
│  - Decode        │
│  - Resize        │
│  - ROI extract   │
└──────────────────┘
       │
       ├──────────────────┬──────────────────┬──────────────────┐
       ▼                  ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Forel-Ule  │   │   Algae     │   │    Foam     │   │  Turbidity  │
│  Colorimetry│   │  Detection  │   │  Detection  │   │  Estimation │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
   FU Index          Algae %           Foam %             Clarity
   (1-21)            (0-100)           (0-100)            (0-100)
       │                  │                  │                  │
       └──────────────────┴──────────────────┴──────────────────┘
                                    │
                                    ▼
                         ┌──────────────────┐
                         │  Composite Risk  │
                         │  Score (0-100)   │
                         └──────────────────┘
                                    │
                                    ▼
                         ┌──────────────────┐
                         │  Risk Level      │
                         │  LOW | MOD | HIGH│
                         └──────────────────┘
```

---

## 1. Pre-Processing

```python
def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Decode and prepare image for analysis."""
    # Decode from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # BGR format
    
    # Resize to standard size (maintain aspect ratio)
    # Max dimension 800px — balances speed vs detail
    h, w = img.shape[:2]
    if max(h, w) > 800:
        scale = 800 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale)
    
    # Extract ROI: center 60% of image (avoid edges/sky/bank)
    h, w = img.shape[:2]
    y_start = int(h * 0.2)
    y_end = int(h * 0.8)
    x_start = int(w * 0.2)
    x_end = int(w * 0.8)
    roi = img[y_start:y_end, x_start:x_end]
    
    return roi
```

**Why center 60%?** Citizens may capture sky, banks, vegetation at edges. The water surface is most likely in the center of a "point camera at water" photo.

---

## 2. Forel-Ule Colorimetric Analysis

### Background
The Forel-Ule (FU) scale is a real limnological standard used since 1892. It maps water color to a 21-point index:
- FU 1-6: Blue (clear, oligotrophic)
- FU 7-9: Blue-green (mesotrophic)
- FU 10-14: Green/Yellow-green (eutrophic)
- FU 15-18: Yellow/Brown (high sediment/organic matter)
- FU 19-21: Brown/Red-brown (heavily polluted)

### Implementation

```python
# Forel-Ule reference colors (RGB) — 21 standard colors
FU_COLORS = [
    (29, 98, 152),    # FU 1 - Deep blue
    (34, 114, 148),   # FU 2
    (40, 130, 140),   # FU 3
    (47, 145, 130),   # FU 4
    (55, 158, 118),   # FU 5
    (65, 168, 105),   # FU 6
    (78, 175, 90),    # FU 7
    (95, 180, 75),    # FU 8
    (115, 183, 60),   # FU 9
    (138, 185, 48),   # FU 10
    (162, 185, 38),   # FU 11
    (185, 182, 30),   # FU 12
    (205, 175, 28),   # FU 13
    (222, 165, 28),   # FU 14
    (235, 152, 30),   # FU 15
    (244, 138, 32),   # FU 16
    (248, 120, 35),   # FU 17
    (250, 100, 38),   # FU 18
    (248, 78, 40),    # FU 19
    (242, 55, 42),    # FU 20
    (232, 32, 45),    # FU 21 - Red-brown (worst)
]

def analyze_forel_ule(roi: np.ndarray) -> dict:
    """
    Extract dominant water color and map to FU index.
    
    Returns:
        {
            "fu_index": int (1-21),
            "fu_color_name": str,
            "dominant_rgb": [r, g, b],
            "quality_score": float (0-100, higher = cleaner)
        }
    """
    # Convert BGR to RGB
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    
    # Reshape to pixel list for k-means
    pixels = rgb.reshape(-1, 3).astype(np.float32)
    
    # K-means clustering (k=3) to find dominant colors
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
    
    # Pick the largest cluster as dominant color
    counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(counts)
    dominant_color = centers[dominant_idx].astype(int)
    
    # Find nearest FU color via Euclidean distance
    min_dist = float('inf')
    fu_index = 1
    for i, fu_color in enumerate(FU_COLORS):
        dist = np.sqrt(np.sum((dominant_color - np.array(fu_color)) ** 2))
        if dist < min_dist:
            min_dist = dist
            fu_index = i + 1
    
    # Map FU index to quality score (1=best → 100, 21=worst → 0)
    quality_score = max(0, 100 - ((fu_index - 1) / 20) * 100)
    
    return {
        "fu_index": fu_index,
        "fu_color_name": FU_COLOR_NAMES[fu_index - 1],
        "dominant_rgb": dominant_color.tolist(),
        "quality_score": round(quality_score, 1)
    }
```

### FU Color Names
```python
FU_COLOR_NAMES = [
    "Indigo Blue", "Dark Blue", "Blue", "Blue-Green", "Green-Blue",
    "Green", "Yellow-Green", "Greenish Yellow", "Yellow",
    "Brownish Yellow", "Yellow-Brown", "Brown-Yellow", "Brownish",
    "Greenish Brown", "Brown", "Dark Brown", "Reddish Brown",
    "Brown-Red", "Dark Red-Brown", "Very Dark Brown", "Near Black"
]
```

---

## 3. Algae Detection (HSV Green Hue Analysis)

### Scientific Basis
Algal blooms cause visible green discoloration. In HSV color space, green hues occupy a specific range that can be reliably detected.

### Implementation

```python
def detect_algae(roi: np.ndarray) -> dict:
    """
    Detect green algae coverage using HSV color space.
    
    Returns:
        {
            "algae_percentage": float (0-100),
            "severity": str ("none", "low", "moderate", "heavy")
        }
    """
    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Green hue range in OpenCV HSV: H=35-85, S>50, V>50
    # (OpenCV uses H: 0-179, S: 0-255, V: 0-255)
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
        "severity": severity
    }
```

---

## 4. Foam Detection (Bright Low-Saturation Blob Detection)

### Scientific Basis
Foam/froth on water appears as bright white/off-white patches — high Value, low Saturation in HSV. Contour analysis identifies discrete foam patches.

### Implementation

```python
def detect_foam(roi: np.ndarray) -> dict:
    """
    Detect foam/froth using HSV thresholding + contour analysis.
    
    Returns:
        {
            "foam_detected": bool,
            "foam_coverage_percentage": float (0-100),
            "foam_patch_count": int
        }
    """
    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Foam characteristics: low saturation + high value (bright white)
    # S < 30 (very desaturated), V > 200 (very bright)
    lower_foam = np.array([0, 0, 200])
    upper_foam = np.array([179, 30, 255])
    
    foam_mask = cv2.inRange(hsv, lower_foam, upper_foam)
    
    # Morphological operations to clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    foam_mask = cv2.morphologyEx(foam_mask, cv2.MORPH_OPEN, kernel)
    foam_mask = cv2.morphologyEx(foam_mask, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(foam_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
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
        "foam_patch_count": len(valid_contours)
    }
```

---

## 5. Turbidity Estimation (Laplacian Variance)

### Scientific Basis
Clear water shows visible depth, texture, and edges (rocks, plants, bottom). Turbid water is uniformly hazy with no edges. The Laplacian operator measures edge intensity — high variance = clear, low variance = turbid.

### Implementation

```python
def estimate_turbidity(roi: np.ndarray) -> dict:
    """
    Estimate water clarity using Laplacian variance (edge detection).
    Higher variance = more edges = clearer water.
    
    Returns:
        {
            "turbidity_score": float (0-100, higher = clearer),
            "laplacian_variance": float (raw value),
            "clarity_description": str
        }
    """
    # Convert to grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # Laplacian (second derivative — detects edges)
    laplacian = cv2.Laplacian(blurred, cv2.CV_64F)
    variance = laplacian.var()
    
    # Normalize to 0-100 scale
    # Empirical range: 0 (completely uniform/turbid) to ~1000+ (very sharp/clear)
    # We cap at 500 for normalization
    max_variance = 500.0
    clarity_score = min(100, (variance / max_variance) * 100)
    
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
        "clarity_description": description
    }
```

---

## 6. Composite Risk Scoring

### Formula

```
composite_score = (algae_percentage × 0.4) 
                + (foam_coverage × 0.3) 
                + ((100 - turbidity_score) × 0.3)
```

- **Algae (40% weight)**: Strongest indicator of eutrophication
- **Foam (30% weight)**: Strong indicator of chemical contamination
- **Inverse Turbidity (30% weight)**: Murky water often indicates suspended pollutants

### Risk Level Classification

| Score Range | Risk Level | Color | Meaning |
|-------------|-----------|-------|---------|
| 0 - 33 | Low | Green (#28a745) | Water appears healthy |
| 34 - 66 | Moderate | Yellow (#ffc107) | Some contamination indicators |
| 67 - 100 | High | Red (#dc3545) | Significant pollution detected |

### Implementation

```python
def calculate_risk_score(algae_pct: float, foam_coverage: float, turbidity_score: float) -> dict:
    """
    Calculate composite risk score from CV components.
    
    Args:
        algae_pct: 0-100 (higher = more algae)
        foam_coverage: 0-100 (higher = more foam)
        turbidity_score: 0-100 (higher = CLEARER, so we invert)
    
    Returns:
        {
            "composite_score": float (0-100),
            "risk_level": str ("low", "moderate", "high"),
            "breakdown": {
                "algae_component": float,
                "foam_component": float,
                "turbidity_component": float
            }
        }
    """
    # Clamp inputs
    algae_pct = max(0, min(100, algae_pct))
    foam_coverage = max(0, min(100, foam_coverage))
    turbidity_score = max(0, min(100, turbidity_score))
    
    # Calculate components
    algae_component = algae_pct * 0.4
    foam_component = foam_coverage * 0.3
    turbidity_component = (100 - turbidity_score) * 0.3  # Invert: low clarity = high risk
    
    # Composite
    composite = algae_component + foam_component + turbidity_component
    composite = max(0, min(100, composite))  # Clamp final score
    
    # Classify
    if composite <= 33:
        risk_level = "low"
    elif composite <= 66:
        risk_level = "moderate"
    else:
        risk_level = "high"
    
    return {
        "composite_score": round(composite, 1),
        "risk_level": risk_level,
        "breakdown": {
            "algae_component": round(algae_component, 2),
            "foam_component": round(foam_component, 2),
            "turbidity_component": round(turbidity_component, 2)
        }
    }
```

---

## Example Scenarios

### Scenario 1: Clean Lake (Sankey Tank)
```
Photo: Clear blue-green water, no foam, visible bottom
├── FU Index: 5 (Green-Blue) → Quality: 80/100
├── Algae: 3.2% → "none"
├── Foam: 0% → not detected
├── Turbidity: 72.5 (clear)
└── Composite: (3.2×0.4) + (0×0.3) + (27.5×0.3) = 1.28 + 0 + 8.25 = 9.5
    → Risk Level: LOW ✅
```

### Scenario 2: Moderate Pollution (Ulsoor Lake)
```
Photo: Greenish water, some surface scum
├── FU Index: 11 (Yellow-Brown) → Quality: 50/100
├── Algae: 28.5% → "moderate"
├── Foam: 5.2% → detected (1 patch)
├── Turbidity: 42.0 (moderately turbid)
└── Composite: (28.5×0.4) + (5.2×0.3) + (58×0.3) = 11.4 + 1.56 + 17.4 = 30.4
    → Risk Level: LOW (borderline moderate)
```

### Scenario 3: Heavy Pollution (Bellandur Lake)
```
Photo: Dark brown water, thick foam, no visibility
├── FU Index: 18 (Brown-Red) → Quality: 15/100
├── Algae: 45.8% → "moderate"
├── Foam: 32.1% → detected (8 patches)
├── Turbidity: 15.0 (highly turbid)
└── Composite: (45.8×0.4) + (32.1×0.3) + (85×0.3) = 18.32 + 9.63 + 25.5 = 53.5
    → Risk Level: MODERATE
```

---

## Limitations & Known Issues

1. **Lighting dependence**: Photos taken in direct sunlight vs shade will produce different FU readings. Guidance helps mitigate.
2. **Reflections**: Sky reflections can skew color analysis. ROI cropping (center 60%) helps but doesn't eliminate.
3. **Non-water objects**: If photo contains mostly vegetation/concrete, results will be meaningless. Future: add water detection pre-check.
4. **Foam false positives**: Bright sand, white objects near water can trigger foam detection.
5. **Turbidity calibration**: The 500 max_variance is empirical. May need tuning with real-world data.

---

## Dependencies

```
opencv-python>=4.8.0
numpy>=1.24.0
```

---

## Future Enhancements (Post-Demo)

- Water region segmentation (detect actual water vs background)
- Temporal comparison (same location over time)
- Multi-photo fusion (multiple angles → better estimate)
- Night/low-light rejection
- Reflection detection and correction
