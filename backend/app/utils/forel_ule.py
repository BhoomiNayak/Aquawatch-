"""
Forel-Ule Color Scale — 21-point limnological standard for water color classification.

Used since 1892 to characterize water body trophic state based on apparent color.
- FU 1-6: Blue tones (oligotrophic, clear)
- FU 7-9: Blue-green (mesotrophic)
- FU 10-14: Green/Yellow-green (eutrophic)
- FU 15-18: Yellow/Brown (high sediment or organic matter)
- FU 19-21: Brown/Red-brown (heavily polluted/dystrophic)
"""

import numpy as np

# Reference RGB colors for the 21 Forel-Ule indices
# Based on published FU scale colorimetric values
FU_COLORS_RGB = [
    (29, 98, 152),    # FU 1  - Deep blue
    (34, 114, 148),   # FU 2  - Blue
    (40, 130, 140),   # FU 3  - Blue
    (47, 145, 130),   # FU 4  - Blue-green
    (55, 158, 118),   # FU 5  - Blue-green
    (65, 168, 105),   # FU 6  - Green-blue
    (78, 175, 90),    # FU 7  - Green
    (95, 180, 75),    # FU 8  - Yellow-green
    (115, 183, 60),   # FU 9  - Yellow-green
    (138, 185, 48),   # FU 10 - Greenish yellow
    (162, 185, 38),   # FU 11 - Yellow-green
    (185, 182, 30),   # FU 12 - Brownish yellow
    (205, 175, 28),   # FU 13 - Brownish
    (222, 165, 28),   # FU 14 - Greenish brown
    (235, 152, 30),   # FU 15 - Brown
    (244, 138, 32),   # FU 16 - Dark brown
    (248, 120, 35),   # FU 17 - Reddish brown
    (250, 100, 38),   # FU 18 - Brown-red
    (248, 78, 40),    # FU 19 - Dark red-brown
    (242, 55, 42),    # FU 20 - Very dark brown
    (232, 32, 45),    # FU 21 - Near black/red
]

# Human-readable color names for each FU index
FU_COLOR_NAMES = [
    "Indigo Blue",        # FU 1
    "Dark Blue",          # FU 2
    "Blue",               # FU 3
    "Blue-Green",         # FU 4
    "Green-Blue",         # FU 5
    "Green",              # FU 6
    "Yellow-Green",       # FU 7
    "Greenish Yellow",    # FU 8
    "Yellow-Green",       # FU 9
    "Greenish Yellow",    # FU 10
    "Yellow-Brown",       # FU 11
    "Brownish Yellow",    # FU 12
    "Brownish",           # FU 13
    "Greenish Brown",     # FU 14
    "Brown",              # FU 15
    "Dark Brown",         # FU 16
    "Reddish Brown",      # FU 17
    "Brown-Red",          # FU 18
    "Dark Red-Brown",     # FU 19
    "Very Dark Brown",    # FU 20
    "Near Black",         # FU 21
]

# Water quality categories based on FU index ranges
FU_QUALITY_CATEGORIES = {
    "excellent": (1, 3),     # Clear, oligotrophic
    "good": (4, 6),          # Slightly colored, still healthy
    "moderate": (7, 10),     # Eutrophic, algae likely
    "poor": (11, 14),        # High nutrient load
    "very_poor": (15, 18),   # High sediment/organic pollution
    "critical": (19, 21),    # Severely degraded
}

# Pre-compute numpy array for vectorized distance calculation
_FU_ARRAY = np.array(FU_COLORS_RGB, dtype=np.float32)


def find_nearest_fu_index(dominant_rgb: tuple[int, int, int]) -> int:
    """
    Find the nearest Forel-Ule index for a given RGB color.
    Uses Euclidean distance in RGB space.

    Args:
        dominant_rgb: (R, G, B) tuple of the dominant water color.

    Returns:
        FU index (1-21).
    """
    color = np.array(dominant_rgb, dtype=np.float32)
    distances = np.sqrt(np.sum((_FU_ARRAY - color) ** 2, axis=1))
    return int(np.argmin(distances)) + 1  # 1-indexed


def get_fu_color_name(fu_index: int) -> str:
    """Get human-readable color name for a FU index (1-21)."""
    if 1 <= fu_index <= 21:
        return FU_COLOR_NAMES[fu_index - 1]
    return "Unknown"


def get_fu_quality_score(fu_index: int) -> float:
    """
    Map FU index to a quality score (0-100).
    FU 1 = 100 (best), FU 21 = 0 (worst). Linear mapping.

    Args:
        fu_index: Forel-Ule index (1-21).

    Returns:
        Quality score (0-100, higher = cleaner water).
    """
    if fu_index < 1:
        fu_index = 1
    if fu_index > 21:
        fu_index = 21
    return round(100 - ((fu_index - 1) / 20) * 100, 1)


def get_fu_quality_category(fu_index: int) -> str:
    """Get quality category string for a FU index."""
    for category, (low, high) in FU_QUALITY_CATEGORIES.items():
        if low <= fu_index <= high:
            return category
    return "unknown"
