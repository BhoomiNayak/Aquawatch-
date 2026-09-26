# AquaWatch — Citizen-Science Water Body Health Monitoring

A citizen-science platform for monitoring water body health. Citizens submit GPS-tagged photos via a mobile app, and the system analyzes them using a **3-model ensemble** (Classical CV + YOLO Segmentation + EfficientNet Classification) to generate water quality scores and risk levels.

## Architecture

```
Photo from citizen phone
         │
         ▼
┌─── 1. CV Pipeline (7 factors) ─────────────────────────┐
│  Forel-Ule colorimetry, algae detection, foam detection │
│  turbidity estimation, oil sheen, color abnormality,    │
│  surface debris detection                               │
│  → Base risk score (0-100) + detailed breakdown         │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─── 2. EfficientNet-B0 (PRIMARY classifier) ────────────┐
│  Trained on 22,376 citizen water photos (EyeOnWater)    │
│  Binary: good / bad water                               │
│  Validation accuracy: 99.8%                             │
│  → Controls whether YOLO boost is applied               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─── 3. YOLOv8n-seg (segmentation) ─────────────────────┐
│  Trained on 949 river water images                      │
│  Classes: clean / turbid / polluted                     │
│  mAP50: 83.6%                                          │
│  → Boosts score ONLY if EfficientNet agrees             │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─── Ensemble Fusion Logic ──────────────────────────────┐
│  If EfficientNet says "bad" (>70%):                     │
│    → Apply EfficientNet boost (+25)                     │
│    → Apply YOLO boost (+15 to +30)                      │
│  If EfficientNet says "good" (>85%):                    │
│    → NO boosts, trust CV score only                     │
│  Safety net: foam>30% or debris>30% → force HIGH        │
└─────────────────────────────────────────────────────────┘
         │
         ▼
    Final Risk Score → LOW / MODERATE / HIGH
```

## Risk Levels

| Score | Level | Color | Meaning |
|-------|-------|-------|---------|
| 0-15 | Low | Green | Water appears healthy |
| 16-35 | Moderate | Yellow | Some pollution indicators |
| 36-100 | High | Red | Significant pollution detected |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + OpenCV + PyTorch |
| ML Models | EfficientNet-B0 + YOLOv8n-seg |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| Dashboard | Vanilla HTML/JS + Leaflet.js |
| Mobile | Flutter 3.x |
| Container | Docker Compose (DB only) |

## Quick Start

### Prerequisites
- Python 3.9+
- Docker Desktop (for PostgreSQL)
- Flutter SDK 3.x (for mobile app)
- NVIDIA GPU (optional, for model training)

### 1. Start the Database
```bash
docker-compose up -d
```

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
pip install ultralytics torch torchvision
```

### 3. Seed Demo Data
```bash
cd backend
python seed.py
```

### 4. Start the Backend
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8001
```
API docs: http://localhost:8001/docs

### 5. Open the Dashboard
Open `dashboard/index.html` in a browser, or:
```bash
cd dashboard
python -m http.server 8080
```

### 6. Run the Mobile App
```bash
cd mobile
flutter pub get
flutter run
```

## Model Training

### EfficientNet (Binary Classifier)
```bash
cd backend
python train_efficientnet.py
# Trains on datasets/EyeOnWater_Dataset/ (good/ and bad/)
# Output: models/efficientnet_water_quality.pt
# Time: ~15 min on RTX 4050
# Accuracy: 99.8%
```

### YOLO Segmentation
```bash
cd backend
python train_model.py
# Trains on datasets/ (clean/turbid/polluted)
# Output: runs/segment/aquawatch/weights/best.pt
# Time: ~20 min on RTX 4050
# mAP50: 83.6%
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/v1/analyze-water | Submit photo for 3-model analysis |
| GET | /api/v1/water-bodies | List all water bodies with risk |
| GET | /api/v1/water-bodies/{id} | Water body detail |
| GET | /api/v1/water-bodies/{id}/history | Risk score history |
| GET | /api/v1/water-bodies/{id}/reports | Reports for a water body |
| GET | /api/v1/health | Health check |

## Project Structure

```
aquawatch/
├── backend/
│   ├── app/
│   │   ├── api/            Route handlers
│   │   ├── models/         SQLAlchemy ORM models
│   │   ├── schemas/        Pydantic schemas
│   │   ├── services/       CV analysis, YOLO, EfficientNet, risk scoring
│   │   └── utils/          Forel-Ule color table
│   ├── models/             Trained model weights (.pt)
│   ├── datasets/           Training datasets
│   ├── seed.py             Demo data seeder
│   ├── train_efficientnet.py
│   └── train_model.py
├── dashboard/              Vanilla HTML/JS + Leaflet map
├── mobile/                 Flutter app
├── docs/                   Planning documents
└── docker-compose.yml
```

## Datasets Used

| Dataset | Images | Purpose |
|---------|--------|---------|
| EyeOnWater | 22,376 (good/bad) | EfficientNet training |
| River Water Quality (Roboflow) | 949 (clean/turbid/polluted) | YOLO segmentation training |
| Water Pollution (Kaggle) | 565 | Threshold calibration |

## How the 7-Factor CV Pipeline Works

1. **Forel-Ule Colorimetry** — Maps water color to 21-point limnological scale
2. **Algae Detection** — Green-hue percentage in HSV color space
3. **Foam Detection** — Bright, low-saturation blob detection with contour analysis
4. **Turbidity Estimation** — Laplacian variance with dark-water penalty
5. **Oil Sheen Detection** — Rainbow iridescence via local hue variance
6. **Color Abnormality** — Statistical distance from natural water colors
7. **Surface Debris** — Contour density analysis for floating objects

## License

CC BY 4.0 (datasets), MIT (code)
