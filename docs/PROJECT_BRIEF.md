# AquaWatch — Complete Project Brief

*Last updated: reflects current implemented state, not just original intent.*

---

## 1. Vision & Problem Statement

### The Problem
India has 3+ million water bodies (lakes, ponds, tanks, wetlands, reservoirs) but only ~700 CPCB monitoring stations, almost entirely on major rivers. Contamination from industrial effluent, sewage, and agricultural runoff goes undetected for months. Visible warning signs — foam, discoloration, algal blooms, oil slicks, floating waste — appear weeks before chemical parameters reach critical levels. No scalable, real-time surveillance exists for smaller water bodies.

### The Vision
A **citizen-science early-warning platform**: ordinary people photograph water bodies with their phones, the system analyzes the image and assigns a pollution risk score, and results surface on a public map dashboard. It is a **triage layer**, not a replacement for lab testing — it tells authorities *where to look first*.

### What AquaWatch Is NOT
- Not a certified water-quality measurement instrument (no NTU, pH, BOD, DO in physical units).
- Not a replacement for CPCB lab analysis.
- Not a real-time chemical sensor network.

It is a **visual-pollution triage and prioritization tool**.

---

## 2. Core User Journey

```
Citizen sees polluted water
      │
      ▼
Opens app → reads photo tips → takes/uploads photo
      │
      ▼
App captures GPS + contamination type + optional name/notes
      │
      ▼
Uploads to backend
      │
      ▼
Backend analyzes image → returns risk score + breakdown
      │
      ▼
App shows color-coded result card (LOW/MODERATE/HIGH + why)
      │
      ▼
Report stored, matched to nearest water body (PostGIS)
      │
      ▼
Public dashboard shows all water bodies on a map, color-coded by risk
```

---

## 3. System Architecture (Current State)

```
┌─────────────────────────────────────────────────────────────┐
│  FLUTTER MOBILE APP                                           │
│  Home → Guidance → Camera/Gallery → Form → Result            │
│  Captures: photo, GPS, contamination type, reporter name     │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP POST /api/v1/analyze-water
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND                                              │
│                                                              │
│  1. CV Pipeline (7 factors) — OpenCV heuristics              │
│     Forel-Ule color, algae, foam, turbidity, oil sheen,      │
│     color abnormality, surface debris                        │
│     → base score + explainability breakdown                  │
│                                                              │
│  2. EfficientNet-B0 — PRIMARY classifier (good/bad)          │
│     → decides whether to trust/boost pollution signal        │
│                                                              │
│  3. YOLOv8-seg — segmentation (clean/turbid/polluted)        │
│     → currently secondary, domain-limited                    │
│                                                              │
│  4. Fusion logic → final composite risk score (0-100)        │
│  5. PostGIS → match report to nearest water body (500m)      │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌──────────────────────┐  ┌──────────────────────────┐
│ PostgreSQL + PostGIS │  │  LEAFLET DASHBOARD       │
│ water_bodies         │  │  Map + colored markers   │
│ reports              │  │  Detail panel per body   │
│ risk_scores          │  │  (browser, vanilla JS)   │
└──────────────────────┘  └──────────────────────────┘
```

---

## 4. Tech Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| Mobile | Flutter 3.x (image_picker, geolocator, http) | ✅ Working |
| Backend | FastAPI + Uvicorn (Python 3.11) | ✅ Working |
| Image Processing | OpenCV 4.x + NumPy | ✅ Working |
| ML Classification | EfficientNet-B0 (PyTorch, transfer learning) | ⚠️ Needs honest re-validation |
| ML Segmentation | YOLOv8n-seg (Ultralytics) | ⚠️ Domain-limited, secondary |
| Database | PostgreSQL 15 + PostGIS 3.3 | ✅ Working |
| ORM | SQLAlchemy 2.0 + GeoAlchemy2 | ✅ Working |
| Dashboard | Vanilla HTML/JS + Leaflet.js | ✅ Working (minimal) |
| Containerization | Docker Compose (DB only) | ✅ Working |
| GPU (training) | NVIDIA RTX 4050 + CUDA 12.1 | ✅ Available |

---

## 5. Risk Scoring Model

### 7-Factor CV Pipeline (Explainability Layer)
1. **Forel-Ule Colorimetry** — dominant water color → 1-21 limnological scale
2. **Algae Detection** — green-hue % in HSV
3. **Foam Detection** — bright low-saturation blob contours
4. **Turbidity Proxy** — Laplacian variance + dark-water penalty
5. **Oil Sheen** — rainbow iridescence + thick-slick dark-patch detection
6. **Color Abnormality** — statistical deviation from natural water colors
7. **Surface Debris** — contour density of floating objects

### Risk Levels
| Score | Level | Color |
|-------|-------|-------|
| 0-15 | Low | Green |
| 16-35 | Moderate | Yellow |
| 36-100 | High | Red |

### Fusion (Current — needs replacement)
EfficientNet is primary authority; YOLO boosts only when EfficientNet agrees; CV provides base + explainability; safety net for extreme foam/debris. **These weights are hand-tuned and must eventually be data-derived.**

---

## 6. Datasets Used

| Dataset | Size | Purpose | Caveat |
|---------|------|---------|--------|
| EyeOnWater (good/bad) | 22,376 augmented | EfficientNet training | Augmented — needs group-aware split |
| River Water Quality (Roboflow) | 949 | YOLO segmentation | Indonesian rivers, domain-limited |
| Water Pollution (Kaggle) | 565 | Threshold calibration | Used for CV tuning |
| Bengaluru seed data | 10 water bodies | Dashboard demo | Synthetic reports |

---

## 7. Constraints

### Technical
- **No ground-truth labels** validated against physical measurement (NTU, chlorophyll, etc.)
- **Datasets are augmented/domain-limited** — accuracy numbers are optimistic
- **Server-side inference only** — 3-8s latency per request
- **Single-machine deployment** — runs on a laptop, not cloud-hosted
- **Hardcoded local IP** in mobile app — breaks on network change

### Operational
- Docker Desktop must be running (DB dependency)
- Phone + laptop must be on same WiFi
- Windows firewall must allow the backend port
- Backend/DB require manual restart after sleep/network change

### Scientific
- CV "measurements" are visual proxies, not calibrated physical units
- Fusion weights are heuristic, not learned
- No baseline comparison against existing methods
- No inter-annotator validation

### Scope (Demo timeline)
- No authentication (reporter name only)
- No satellite/GEE integration (Phase 2)
- No alert system (email/SMS) — Phase 2
- Single photo per report

---

## 8. What's Built vs. Pending

### ✅ Complete & Working
- Flutter app: camera, gallery, GPS, form, result screen with full breakdown
- Backend: `/analyze-water`, `/water-bodies`, `/water-bodies/{id}`, history, reports, health
- 7-factor CV pipeline (including thick oil-slick detection)
- EfficientNet-B0 trained + integrated
- YOLOv8-seg trained + integrated (secondary)
- PostgreSQL + PostGIS with spatial matching
- Leaflet dashboard with color-coded markers + detail panel
- Docker Compose for DB
- Seed script (10 Bengaluru water bodies + history)

### ⚠️ Half-Built / Needs Work
- Dashboard historical trend chart (data served, UI not rendering)
- EfficientNet validation (accuracy inflated by augmented-data leakage)
- Fusion logic (hand-tuned, not data-derived)

### ❌ Not Built (Phase 2)
- Alert system (email/SMS to pollution officers)
- Satellite data integration (GEE — NDWI, chlorophyll-a, TSS)
- Authentication / user accounts
- Offline queue with auto-upload
- Cloud deployment
- Ground-truth validation set

---

## 9. Known Weaknesses (Honest)

1. **EfficientNet 99.8% accuracy is not trustworthy** — augmented images likely leaked across train/val split. Real accuracy is lower (est. 80-88%).
2. **YOLO is domain-mismatched** — trained on Indonesian rivers, misclassifies other water. Currently suppressed in scoring, so it's mostly dead weight.
3. **No physical calibration** — turbidity = edge sharpness, not NTU. Forel-Ule never checked against a spectrophotometer.
4. **Fusion is hand-tuned** — magic numbers, not learned weights.
5. **Fragile ops** — hardcoded IP, manual restarts, laptop-only.

---

## 10. Roadmap to Credibility

### Phase A — Honest Validation (highest priority)
- Re-split EyeOnWater by source image (group-aware), retrain, report real accuracy
- Build a small hand-labeled test set (150-300 real photos, multi-annotator)
- Report precision/recall/confusion matrix, not just accuracy

### Phase B — Simplify & Justify
- Remove YOLO + Roboflow from scoring path (keep YOLO only for region visualization if desired)
- Replace `if/elif` fusion with a small data-derived model (logistic regression on validation set)
- Reframe CV outputs as "visual indicators" not "measurements"

### Phase C — Deployability
- Containerize backend, config-driven IP, auto-start DB
- Finish dashboard trend chart
- Add basic alert stub

### Phase D — Phase 2 Features
- Satellite integration, alerts, auth, offline queue, cloud hosting

---

## 11. Research Positioning

**Most defensible paper framing (achievable now):**
> "AquaWatch: A deployable citizen-science pipeline for water-body pollution triage combining explainable classical computer vision with deep image classification and spatial aggregation."

Contribution = the **system, the explainability layer, and PostGIS spatial aggregation** — NOT raw accuracy claims. Honest numbers + a real (small) validation set make this publishable at a systems/HCI/environmental-informatics venue.

**For a rigorous ML paper**, Phase A must be completed first: group-aware splits, labeled test set, baseline comparison, calibrated metrics, ablation study.

---

## 12. One-Line Summary

**AquaWatch is a citizen-science mobile + backend + dashboard system that triages water-body pollution from phone photos using explainable CV plus deep classification, with PostGIS spatial aggregation — currently a working demo that needs honest validation before it can claim scientific accuracy.**
