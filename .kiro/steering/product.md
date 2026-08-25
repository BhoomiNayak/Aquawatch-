# AquaWatch - Product Summary

AquaWatch is a citizen-science water body health monitoring platform. Users submit geotagged photos of water bodies, and the system runs a 7-factor computer vision analysis pipeline to assess pollution levels and assign risk scores.

## Core Workflow

1. A user submits a photo of a water body along with GPS coordinates, contamination type, and optional notes.
2. The backend runs OpenCV-based image analysis: Forel-Ule colorimetry, algae detection, foam detection, turbidity estimation, oil sheen detection, color abnormality analysis, and surface debris detection.
3. A composite risk score (0-100) is calculated from weighted CV outputs and classified as low/moderate/high.
4. The system matches the report to the nearest known water body (within 500m via PostGIS) or creates a new one.
5. A dashboard displays water bodies on a map with risk levels, historical trends, and report details.

## Key Domain Concepts

- **Water Body**: A tracked lake, river, or pond with denormalized risk score and report count.
- **Report**: A single photo submission with CV analysis results and composite risk score.
- **Risk Score**: A time-series snapshot of a water body's risk level for trend tracking.
- **Forel-Ule Index**: A 1-21 scale colorimetric classification of water color quality.
- **Contamination Types**: industrial_discharge, sewage, algal_bloom, solid_waste, agricultural_runoff, fish_kill, foam, oil_spill, others.
- **Risk Levels**: low (0-15), moderate (16-35), high (36-100).

## Target Users

Citizen scientists, environmental volunteers, and municipal water quality monitors in urban areas (currently focused on Bengaluru, Karnataka).
