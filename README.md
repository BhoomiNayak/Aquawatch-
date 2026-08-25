# AquaWatch — Citizen-Science Water Body Health Monitoring

A citizen-science platform for monitoring water body health. Citizens submit GPS-tagged photos via a mobile app, and the system analyzes them using **classical computer vision + colorimetry** to generate water quality scores and risk levels.

## How It Works

```
Citizen takes photo → Uploads to backend → 7-factor CV analysis → Risk score → Map dashboard
```

### 7-Factor Analysis Pipeline (No ML Required)

1. **Forel-Ule Colorimetry** — Maps water color to the 21-point limnological scale
2. **Algae Detection** — Green-hue percentage in HSV space
3. **Foam Detection** — Bright, low-saturation blob detection
4. **Turbidity Estimation** — Laplacian variance (edge sharpness)
5. **Oil Sheen Detection** — Rainbow iridescence via hue variance
6. **Color Abnormality** — Statistical distance from natural water colors
7. **Surface Debris** — Contour density analysis for floating objects

### Risk Levels

| Score | Level | Color |
|-------|-------|-------|
| 0-15 | Low | Green |
| 16-35 | Moderate | Yellow |
| 36-100 | High | Red |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + OpenCV + NumPy |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| Dashboard | Vanilla HTML/JS + Leaflet.js |
| Mobile | Flutter 3.x |
| Container | Docker Compose (DB only) |

## Quick Start

### Prerequisites

- Python 3.9+
- Docker Desktop (for PostgreSQL)
- Flutter SDK 3.x (for mobile app)

### 1. Start the Database

```bash
docker-compose up -d
```

This starts PostgreSQL + PostGIS on port 5432.

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Seed Demo Data

```bash
cd backend
python seed.py
```

Inserts 10 Bengaluru water bodies with sample reports and risk history.

### 4. Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

### 5. Open the Dashboard

```bash
cd dashboard
python -m http.server 8080
```

Then open http://localhost:8080 in your browser.

Or simply open `dashboard/index.html` directly.

### 6. Run the Mobile App

```bash
cd mobile
flutter pub get
flutter run
```

For Android emulator: backend is accessible at `http://10.0.2.2:8000`
For physical device: update `api_service.dart` with your machine's local IP.

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/v1/analyze-water | Submit photo for analysis |
| GET | /api/v1/water-bodies | List all water bodies with risk |
| GET | /api/v1/water-bodies/{id} | Water body detail |
| GET | /api/v1/water-bodies/{id}/history | Risk score history |
| GET | /api/v1/water-bodies/{id}/reports | Reports for a water body |
| GET | /api/v1/health | Health check |

## Project Structure

```
aquawatch/
├── backend/           FastAPI + OpenCV backend
│   ├── app/
│   │   ├── api/       Route handlers
│   │   ├── models/    SQLAlchemy ORM models
│   │   ├── schemas/   Pydantic schemas
│   │   ├── services/  CV analysis, risk scoring, water body matcher
│   │   └── utils/     Forel-Ule color table
│   ├── seed.py        Demo data seeder
│   └── test_*.py      Test scripts
├── dashboard/         Vanilla HTML/JS + Leaflet map
├── mobile/            Flutter app
├── docs/              Planning documents
└── docker-compose.yml PostgreSQL + PostGIS
```

## Testing the CV Pipeline

```bash
cd backend
# Synthetic tests
python test_cv_pipeline.py

# Real images (add photos to test_images/ first)
python test_real_images.py

# Full API flow simulation
python test_api_flow.py
```

## Demo Flow

1. Open dashboard in browser — see 10 water bodies on map
2. Open Flutter app on phone/emulator
3. Tap "Report Water Quality"
4. Read photo tips, open camera
5. Take a photo of water
6. Select contamination type, submit
7. See color-coded result card with 7-factor breakdown
8. Refresh dashboard — new report appears on map

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

```
DATABASE_URL=postgresql://aquawatch:aquawatch_dev@localhost:5432/aquawatch
HOST=0.0.0.0
PORT=8000
DEBUG=true
CORS_ORIGINS=*
```

## Notes

- No authentication (demo mode)
- Images are processed and discarded (not stored)
- Thresholds calibrated from 565 real-world polluted water images
- Dashboard auto-refreshes every 30 seconds
