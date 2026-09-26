# AquaWatch — Frozen Baseline (baseline_v1)

**Frozen on:** first honest-validation cycle, before any labeled Indian benchmark.
**Purpose:** A stable reference point. Do NOT change scoring logic until the
ablation study (post-labeling) tells us what to change. Every change after this
point must be measured against baseline_v1.

---

## Frozen Components

### CV Pipeline (7 factors) — `app/services/cv_analysis.py`
- Forel-Ule colorimetry (k-means dominant colour → FU 1-21)
- Algae (HSV green %)
- Foam (bright low-sat blobs)
- Turbidity (Laplacian variance + dark-water penalty)
- Oil sheen (rainbow iridescence + thick dark-slick detection)
- Color abnormality (deviation from natural water colours)
- Surface debris (contour density)
- ROI: center 80% crop (NOT water-masked yet — Step 3 pending)

### Risk Scoring — `app/services/risk_scoring.py`
- Weights: algae 0.15, foam 0.18, turbidity 0.18, forel_ule 0.10,
  oil 0.07, color_abnormality 0.15, debris 0.17
- Thresholds: LOW ≤ 15, MODERATE ≤ 35, HIGH > 35
- **These are hand-tuned. To be replaced by logistic regression (Step 5) after labels.**

### Fusion Logic — `app/api/reports.py`
- EfficientNet = primary authority (bad >0.70 → boost; good >0.85 → trust CV)
- YOLO = secondary (boosts only when EfficientNet agrees)
- Roboflow = disabled (latency)
- **Hand-tuned magic numbers. To be replaced/validated by ablation.**

### Models
- EfficientNet-B0 (group-aware pHash split): `models/efficientnet_water_quality_group_aware.pt`
  - Internal val acc: 99.9% (leakage audit: NONE, min cross-split Hamming = 12)
- YOLOv8n-seg: `runs/segment/runs/segment/aquawatch/weights/best.pt`
  - mAP50: 83.6% (on Indonesian river test split only)

---

## Pre-Label Sanity Check (Indian test set, 200 images, UNLABELED)

Ran full pipeline on 200 Indian images. **These are predictions, NOT accuracy.**

| Model | Distribution | Observation |
|-------|-------------|-------------|
| CV composite | 87% MODERATE, 4.5% low, 8.5% high | Collapses to moderate — poor discrimination |
| EfficientNet | 94.5% "bad", 5.5% "good" | Severe single-class bias on Indian domain |
| YOLO | 51% no-detection, 25.5% clean, 23% turbid, 0.5% polluted | Detection failure on half — domain mismatch |

**Key finding (paper-worthy):** Models trained on non-Indian distributions show
severe prediction bias on Indian water bodies. This justifies the domain-specific
benchmark. This is an HONEST finding, not a failure — it's the motivation.

---

## What Must NOT Change Until Ablation

1. Do not retune risk_scoring weights or thresholds.
2. Do not change fusion logic in reports.py.
3. Do not implement water masking (Step 3) yet.
4. Do not change EfficientNet or YOLO weights.

## What Happens Next (in order, after labels land)

1. Measure EfficientNet-only accuracy on labeled Indian set → the real number.
2. Run ablation: CV-only vs EfficientNet-only vs YOLO-only vs ensemble.
3. Let the ablation table decide what to keep/fix/delete.
4. Only then: water masking, logistic fusion, calibration.

---

*This file is the contract. If you change frozen logic before the ablation,
you lose the ability to measure whether it helped.*
