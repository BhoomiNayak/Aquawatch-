# AquaWatch - Project Structure

## Directory Layout

```
aquawatch/
├── docs/                           # Planning documents
│   ├── PROJECT_STRUCTURE.md
│   ├── ARCHITECTURE.md
│   ├── API_DESIGN.md
│   ├── DATABASE_SCHEMA.md
│   ├── CV_PIPELINE.md
│   ├── FRONTEND_PLAN.md
│   ├── MOBILE_APP_PLAN.md
│   └── IMPLEMENTATION_ROADMAP.md
│
├── backend/                        # FastAPI + OpenCV backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry, CORS, router includes
│   │   ├── config.py             # Environment variables & settings
│   │   ├── database.py           # SQLAlchemy engine + session
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── water_body.py
│   │   │   ├── report.py
│   │   │   └── risk_score.py
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── report.py
│   │   │   ├── water_body.py
│   │   │   └── analysis.py
│   │   ├── api/                  # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── reports.py        # POST /analyze-water
│   │   │   └── water_bodies.py   # GET /water-bodies, GET /water-bodies/{id}/history
│   │   ├── services/             # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── cv_analysis.py    # OpenCV image analysis (FU, algae, foam, turbidity)
│   │   │   ├── risk_scoring.py   # Composite score calculation
│   │   │   ├── water_body_matcher.py  # PostGIS proximity matching
│   │   │   └── alerts.py        # Email alerts (nice-to-have)
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── forel_ule.py      # FU color scale lookup table
│   ├── seed.py                    # Seed script: 10 Bengaluru water bodies + mock history
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── dashboard/                      # Vanilla HTML/JS/CSS + Leaflet
│   ├── index.html                 # Single page with map + side panel
│   ├── script.js                  # Fetch API, Leaflet map logic, event handlers
│   ├── style.css                  # Styling, responsive layout
│   └── assets/
│       └── logo.png              # AquaWatch logo (optional)
│
├── mobile/                         # Flutter mobile app
│   ├── lib/
│   │   ├── main.dart             # App entry, MaterialApp, routes
│   │   ├── screens/
│   │   │   ├── home_screen.dart           # Main screen with "Report" button
│   │   │   ├── guidance_screen.dart       # Photo-taking instructions
│   │   │   ├── camera_screen.dart         # Camera capture
│   │   │   ├── report_form_screen.dart    # Contamination type + name
│   │   │   └── result_screen.dart         # Color-coded result card
│   │   ├── models/
│   │   │   └── report.dart               # Report data model
│   │   ├── services/
│   │   │   ├── api_service.dart          # HTTP calls to backend
│   │   │   └── location_service.dart     # GPS capture
│   │   └── widgets/
│   │       ├── contamination_dropdown.dart
│   │       ├── result_card.dart          # Score + breakdown display
│   │       └── risk_indicator.dart       # Color-coded risk badge
│   ├── pubspec.yaml
│   └── android/
│
├── docker-compose.yml              # PostgreSQL + PostGIS
├── .env.example
├── .gitignore
└── README.md
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI (Python 3.9+) | REST API, image processing orchestration |
| Image Analysis | OpenCV + NumPy | Forel-Ule, algae/foam/turbidity detection |
| Database | PostgreSQL 15 + PostGIS 3.3 | Spatial queries, report storage |
| ORM | SQLAlchemy 2.0 + GeoAlchemy2 | Database access with PostGIS support |
| Dashboard | Vanilla HTML/JS/CSS + Leaflet.js | Interactive map, no build step |
| Mobile | Flutter 3.x | Camera, GPS, upload, results display |
| Containerization | Docker Compose | PostgreSQL container for dev |

## Module Responsibilities

### Backend (`/backend`)
- **cv_analysis.py**: Core image processing — extracts FU index, algae %, foam detection, turbidity
- **risk_scoring.py**: Combines CV outputs into composite score (0-100) and risk level
- **water_body_matcher.py**: Finds nearest water body using PostGIS proximity query
- **reports.py**: Handles photo upload, orchestrates analysis, stores results
- **water_bodies.py**: Serves water body list + history for dashboard
- **seed.py**: Populates DB with 10 Bengaluru water bodies + fake historical data

### Dashboard (`/dashboard`)
- Single-page vanilla app — no build tools, no npm
- Leaflet map centered on Bengaluru with colored circle markers
- Click marker → side panel shows details + trend
- Auto-refreshes every 30 seconds (or manual refresh button)

### Mobile (`/mobile`)
- Simplified Flutter app — no on-device processing
- Flow: Home → Guidance → Camera → Form → Submit → Results
- Shows color-coded result card with breakdown after submission
- GPS captured automatically in background

## Key Design Decisions

1. **No ML** — Classical CV (Forel-Ule + HSV analysis) needs zero training data
2. **Server-side analysis** — OpenCV runs on backend, mobile just uploads photos
3. **No auth** — Reporter name field only, no login for demo
4. **No satellite data** — Phase 2; scoring is purely from submitted photos
5. **Vanilla dashboard** — No React, no build step, opens in any browser
6. **PostGIS proximity** — 500m radius matching, auto-creates unnamed water bodies
7. **Single photo** — One photo per report for demo simplicity
