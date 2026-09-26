# AquaWatch — Cross-Modal Citizen-Science Water-Quality Triage

AquaWatch monitors urban water-body health from two complementary signals:

1. **Ground layer** — citizens submit a GPS-tagged photo; a server-side pipeline (classical CV + a deep classifier) produces a 0–100 risk score and Low/Moderate/High level.
2. **Satellite layer** — Sentinel-2 imagery (via Google Earth Engine) provides an **independent** physical corroboration signal (NDCI, a chlorophyll/eutrophication proxy) for water bodies large enough to resolve.

> **On accuracy — read this first.** The image classifier reaches ~99.9% on its in-distribution validation set but **collapses to chance (ROC-AUC ≈ 0.49) on a real, human-labeled Indian benchmark**. AquaWatch is therefore presented honestly as a **triage + corroboration** system, not a calibrated measurement tool. The satellite layer is the constructive contribution: it discriminates eutrophic from clear water where the ground classifier does not. See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) for the full experimental record.

## Architecture

```
Citizen photo + GPS
        │
        ▼
┌─ Ground layer (FastAPI) ───────────────────────────────┐
│  1. 7-factor CV pipeline (OpenCV) → base risk 0–100     │
│     Forel-Ule, algae, foam, turbidity, oil sheen,       │
│     colour abnormality, surface debris                  │
│  2. EfficientNet-B0 (binary clean/polluted) — primary   │
│  3. YOLOv8n-seg (clean/turbid/polluted) — secondary*    │
│  → composite risk score → Low / Moderate / High         │
└─────────────────────────────────────────────────────────┘
        │  (report saved immediately, 201 processing_satellite)
        ▼
┌─ PostGIS matching ─────────────────────────────────────┐
│  nearest known water body within 500 m (ST_DWithin)     │
└─────────────────────────────────────────────────────────┘
        │  (async — FastAPI BackgroundTasks)
        ▼
┌─ Satellite corroboration (Google Earth Engine) ────────┐
│  Cached tier:  6 tracked lakes, monthly NDCI series     │
│  On-demand tier: arbitrary GPS → buffered live query    │
│  NDWI water mask → NDCI vs clean-reference baseline      │
│  → verdict: elevated / watch / nominal / unavailable    │
└─────────────────────────────────────────────────────────┘
        │
        ▼
   Dashboard (Leaflet) + Mobile result view
   (poll GET /reports/{id} until satellite verdict is done)
```

\* YOLO is retained in the scoring path for ablation, but the benchmark shows it is domain-mismatched (Indonesian rivers) and hurts on Indian water; the methodology recommends dropping it from production. See findings below.

## Validation & honest findings

Evaluated on a curated, human-labeled Indian benchmark (N=200, 3 annotators, Fleiss κ = 0.76 severity / 0.80 binary; base rate 64.5% polluted).

| Model (binary) | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| CV-only | 56.5% | 61.7% | 86.1% | 71.8% |
| EfficientNet-only | 61.0% | 63.5% | 93.0% | 75.5% |
| YOLO-only | 43.8% | 68.0% | 30.1% | 41.7% |
| Ensemble | 64.5% | 64.6% | 99.2% | 78.3% |

- **OOD collapse:** classifier ROC-AUC = **0.49** (chance); internal val 99.9% → benchmark 55–61%.
- **Ensemble ≈ base rate:** 64.5% accuracy = predicting "polluted" almost always (not skill).
- **Threshold recalibration does not fix it:** 5-fold Youden's J recovers specificity 2.8% → 32.4% but accuracy drops to 55% — no threshold repairs a non-discriminative model.
- **Satellite works where the classifier fails:** monthly-median NDCI cleanly separates polluted urban lakes (Hussain Sagar 0.26, Bellandur 0.19) and eutrophic Ulsoor (0.35) from clean references (Hesaraghatta ≈0.02, Pangong −0.08).

## Risk levels

| Score | Level | Meaning |
|---|---|---|
| 0–15 | Low | Water appears healthy |
| 16–35 | Moderate | Some pollution indicators |
| 36–100 | High | Significant pollution detected |

## Satellite corroboration verdict

Each report is enriched asynchronously with a satellite verdict:

| Field | Meaning |
|---|---|
| `status` | processing → done / unavailable / error |
| `ndci` | mean NDCI over water pixels (chlorophyll proxy) |
| `exceeds_clean_baseline` | NDCI above the clean-reference baseline (≈0.0155) |
| `spatial_confidence` | high / medium / low (buffer at which water was found) |
| `mode` | `cached_lake` (Tracked Lake) or `on_demand_point` (Dynamic Point Buffer) |
| `corroboration` | elevated / watch / nominal / unavailable |

The satellite signal is **not** probabilistically fused with the classifier (blending a chance-level signal adds noise); it is a complementary, independent layer. Anomaly scoring is **relative** (vs clean references / own history), never absolute mg/m³.

## Tech stack

| Component | Technology |
|---|---|
| Backend | FastAPI + OpenCV + PyTorch |
| ML models | EfficientNet-B0 + YOLOv8n-seg |
| Satellite | Google Earth Engine (`earthengine-api`), Sentinel-2 L2A |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| Dashboard | Vanilla HTML/JS + Leaflet.js |
| Mobile | Flutter 3.x |
| Container | Docker Compose (DB only) |

## Quick start

### Prerequisites
- Python 3.10+
- Docker Desktop (PostgreSQL/PostGIS)
- Flutter SDK 3.x (mobile app)
- A Google Earth Engine project (for the satellite layer)

### 1. Start the database
```bash
docker compose up -d          # PostGIS on port 5433
```

### 2. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Start the backend
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8002
```
API docs: http://localhost:8002/docs  (tables auto-create on startup)

### 4. (Optional) Satellite layer — Google Earth Engine
The ground pipeline works without this; the satellite verdict simply returns `unavailable` until configured.

1. Create a GEE-enabled Google Cloud project and a **service account** with roles **Service Usage Consumer** + **Earth Engine Resource Writer**.
2. Download its JSON key to `backend/keys/` (any filename — it is auto-detected; the folder is git-ignored).
3. Precompute the tracked-lake NDCI series:
   ```bash
   cd backend
   python scripts/sentinel_ndci_timeseries.py --project <YOUR_GEE_PROJECT_ID>
   ```

### 5. Open the dashboard
```bash
cd dashboard
python -m http.server 8080
```

### 6. Run the mobile app
```bash
cd mobile
flutter pub get
flutter run
```
Set `baseUrl` in `mobile/lib/services/api_service.dart` to your machine's IP (`http://<LAN_IP>:8002/api/v1`).

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/analyze-water` | Submit photo; returns `201` + `status: processing_satellite`; dispatches async satellite enrichment |
| GET | `/api/v1/reports/{id}` | Single report incl. `satellite_verdict` (poll until `status == done`) |
| GET | `/api/v1/reports` | List recent reports with satellite verdicts |
| GET | `/api/v1/water-bodies` | List water bodies with risk |
| GET | `/api/v1/water-bodies/{id}` | Water body detail |
| GET | `/api/v1/water-bodies/{id}/history` | Risk score history |
| GET | `/api/v1/water-bodies/{id}/reports` | Reports for a water body (with satellite verdict) |
| GET | `/api/v1/health` | Health check |

## Datasets

| Dataset | Size | Labels | Role | License |
|---|---|---|---|---|
| EyeOnWater | 22,376 (good/bad) | binary | EfficientNet training | research-use (not redistributed) |
| Indian benchmark (`local_benchmark`) | 200 | 3-class severity + consensus | **evaluation only** | image provenance to document |
| Pollution-type set | 223 (8 categories) | pollution type | CV-detector validation | **CC, attributed** |
| River segmentation (Roboflow) | 949 | clean/turbid/polluted + masks | YOLO training | CC-BY-4.0 |

Bulk image datasets, trained weights (`.pt`), and generated `reports/` are git-ignored (size + image licensing); regenerate them with the scripts below.

## Project structure

```
aquawatch/
├── backend/
│   ├── app/
│   │   ├── api/            reports.py (+ async satellite enrichment), water_bodies.py
│   │   ├── models/         SQLAlchemy ORM (report incl. satellite_* columns)
│   │   ├── schemas/        Pydantic schemas
│   │   ├── services/       cv_analysis, risk_scoring, yolo_detector,
│   │   │                   satellite.py (cached + on-demand NDCI)
│   │   └── main.py         startup + idempotent column migration
│   ├── scripts/            calibration, ablation, sentinel time-series,
│   │                       manuscript-asset exporter, leakage audit
│   ├── datasets/           target_lakes.geojson, benchmark CSV (images ignored)
│   ├── keys/               GEE service-account key (git-ignored)
│   └── reports/            generated figures/metrics (git-ignored)
├── dashboard/              Leaflet map + satellite verdict badges
├── mobile/                 Flutter app (polls report satellite verdict)
├── docs/                   METHODOLOGY.md, PROJECT_BRIEF.md
└── docker-compose.yml
```

## Reproducing the research

```bash
cd backend
python phash_group_split.py                         # de-leak EyeOnWater (group-aware)
python train_efficientnet_group_aware.py            # train classifier on clean split
python scripts/ablation_harness.py --benchmark local # ablation table
python scripts/calibrate_threshold.py               # 5-fold Youden recalibration + OOD gap
python scripts/sentinel_ndci_timeseries.py --project <ID>  # Sentinel-2 NDCI series
python scripts/export_manuscript_assets.py          # figures + Table 1 → reports/
```

## Documentation

- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — full methodology, datasets, experiments, results, limitations, reproducibility.
- [`backend/BASELINE.md`](backend/BASELINE.md) — frozen baseline contract.

## License

CC BY 4.0 (documentation & derived figures), MIT (code). Training/benchmark images retain their original licenses and are not redistributed here.
