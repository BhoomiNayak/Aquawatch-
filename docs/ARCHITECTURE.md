# AquaWatch - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CITIZEN (Mobile App)                       │
│                                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │ Guidance │──▶│  Camera  │──▶│  Report  │──▶│  Upload to  │  │
│  │  Screen  │   │  Capture │   │   Form   │   │   Backend   │  │
│  └──────────┘   └──────────┘   └──────────┘   └─────────────┘  │
│                      │                               │           │
│                      ▼                               │           │
│                 ┌──────────┐                         │           │
│                 │   GPS    │─────────────────────────┘           │
│                 │  Auto-tag│                                     │
│                 └──────────┘                                     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼ HTTP POST /api/v1/analyze-water
┌──────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                           │
│                                                                    │
│  ┌───────────┐   ┌─────────────────┐   ┌─────────────────────┐  │
│  │ API Layer │──▶│  CV Analysis    │──▶│  Risk Scoring       │  │
│  │ (routes)  │   │  - Forel-Ule    │   │  - Composite calc   │  │
│  │           │   │  - Algae detect  │   │  - Level classify   │  │
│  │           │   │  - Foam detect   │   │                     │  │
│  │           │   │  - Turbidity     │   │                     │  │
│  └───────────┘   └─────────────────┘   └─────────────────────┘  │
│        │                                         │                │
│        ▼                                         ▼                │
│  ┌───────────────┐                    ┌───────────────────────┐  │
│  │  PostGIS      │                    │  Alert Service        │  │
│  │  Water Body   │                    │  (nice-to-have)       │  │
│  │  Matcher      │                    │                       │  │
│  └───────────────┘                    └───────────────────────┘  │
│        │                                                          │
│        ▼                                                          │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL + PostGIS Database                  │   │
│  │  water_bodies | reports | risk_scores                      │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼ HTTP GET /api/v1/water-bodies
┌──────────────────────────────────────────────────────────────────┐
│                   DASHBOARD (Vanilla HTML/JS + Leaflet)            │
│                                                                    │
│  ┌──────────────┐   ┌────────────────┐   ┌───────────────────┐  │
│  │  Leaflet Map │   │  Detail Panel  │   │  Summary Stats    │  │
│  │  (markers)   │   │  (side panel)  │   │  (header bar)     │  │
│  └──────────────┘   └────────────────┘   └───────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Report Submission Flow (Primary - Must Work for Demo)

```
Citizen opens app
  → Sees guidance screen: "Point camera at water surface, avoid reflections"
  → Takes photo of water body
  → GPS coordinates auto-captured in background (<10m accuracy)
  → Citizen selects contamination type from dropdown
  → Citizen enters name (optional)
  → App uploads photo + GPS + metadata to POST /api/v1/analyze-water
    → Payload: multipart/form-data with image file + JSON metadata
  → Backend receives image
  → Backend runs CV analysis pipeline:
    1. Forel-Ule colorimetric index (dominant water color → FU 1-21)
    2. Algae detection (green-hue % in HSV space)
    3. Foam detection (bright, low-saturation blob contours)
    4. Turbidity estimation (Laplacian variance = edge sharpness)
  → Backend calculates composite risk score (0-100)
  → Backend finds nearest water body via PostGIS (500m radius)
    → If none found → auto-create "Unnamed Water Body" at those coords
  → Backend stores report + analysis in database
  → Backend recalculates water body risk level
  → Response returns full analysis breakdown to app
  → App shows color-coded result card to citizen
```

### 2. Dashboard View Flow (Must Work for Demo)

```
User opens index.html in browser
  → JavaScript calls GET /api/v1/water-bodies
  → Backend queries all water bodies with current risk scores
  → Returns: [{ id, name, lat, lng, risk_level, risk_score, report_count, ... }]
  → Leaflet renders circle markers on map:
    - Green (#28a745): Low Risk (0-33)
    - Yellow/Orange (#ffc107): Moderate Risk (34-66)
    - Red (#dc3545): High Risk (67-100)
  → User clicks a marker
  → JavaScript calls GET /api/v1/water-bodies/{id}
  → Side panel shows:
    - Water body name + risk level badge
    - Composite score + individual component scores
    - Last 5 reports summary
    - Risk trend (if history available)
```

### 3. CV Analysis Pipeline (Server-Side)

```
Input: JPEG/PNG image (uploaded by citizen)
  │
  ├─▶ [1] Decode image → OpenCV BGR matrix
  │
  ├─▶ [2] Forel-Ule Analysis
  │       → Convert to RGB
  │       → Mask water region (center 60% of image)
  │       → Calculate dominant color (k-means with k=3, pick largest cluster)
  │       → Find nearest FU index via Euclidean distance to FU color table
  │       → Map FU index to quality score (FU 1-6 = good, 7-14 = moderate, 15-21 = poor)
  │
  ├─▶ [3] Algae Detection
  │       → Convert to HSV
  │       → Create mask: H=35-85 (green range), S>50, V>50
  │       → algae_percentage = (green_pixels / total_pixels) × 100
  │
  ├─▶ [4] Foam Detection
  │       → Convert to HSV
  │       → Create mask: S<30, V>200 (bright + low saturation = white foam)
  │       → Find contours, filter by area (min 500px)
  │       → foam_detected = True/False
  │       → foam_coverage = (foam_pixels / total_pixels) × 100
  │
  ├─▶ [5] Turbidity Estimation
  │       → Convert to grayscale
  │       → Apply Laplacian filter
  │       → turbidity_score = normalized variance (high variance = clear, low = turbid)
  │
  └─▶ [6] Composite Risk Score
          → score = (algae_pct × 0.4) + (foam_coverage × 0.3) + ((100 - clarity) × 0.3)
          → Clamp to 0-100
          → Classify: LOW (0-33) | MODERATE (34-66) | HIGH (67-100)
```

### 4. Water Body Matching (PostGIS)

```sql
-- Find nearest water body within 500m of report GPS
SELECT id, name,
       ST_Distance(
         location::geography,
         ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
       ) as distance_meters
FROM water_bodies
WHERE ST_DWithin(
    location::geography,
    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
    500  -- 500 meters
)
ORDER BY distance_meters
LIMIT 1;
```

- If found → assign report to that water body
- If not found → INSERT new water body ("Unnamed Water Body near [lat, lng]")

## Pre-Seeded Water Bodies (Bengaluru)

| # | Name | Lat | Lng | Type |
|---|------|-----|-----|------|
| 1 | Ulsoor Lake | 12.9825 | 77.6200 | Lake |
| 2 | Sankey Tank | 13.0080 | 77.5730 | Tank |
| 3 | Bellandur Lake | 12.9373 | 77.6784 | Lake |
| 4 | Yediyur Lake | 12.9380 | 77.5700 | Lake |
| 5 | Puttenahalli Lake | 12.8900 | 77.5880 | Lake |
| 6 | Agara Lake | 12.9250 | 77.6380 | Lake |
| 7 | Lalbagh Lake | 12.9507 | 77.5848 | Lake |
| 8 | Kaikondrahalli Lake | 12.9100 | 77.6740 | Lake |
| 9 | Jakkur Lake | 13.0700 | 77.6100 | Lake |
| 10 | Hennur Lake | 13.0450 | 77.6350 | Lake |

## Deployment Architecture (Demo - Localhost)

```
localhost:
├── :5432  → PostgreSQL 15 + PostGIS 3.3 (Docker container)
├── :8000  → FastAPI backend (uvicorn --reload --host 0.0.0.0 --port 8000)
└── :8080  → Dashboard (python -m http.server 8080 in /dashboard)

Android Emulator:
└── Flutter app → http://10.0.2.2:8000 (Android emulator loopback to host)

Physical Device (same WiFi):
└── Flutter app → http://<your-local-ip>:8000
```

## Docker Compose (DB Only)

```yaml
version: '3.8'
services:
  db:
    image: postgis/postgis:15-3.3
    container_name: aquawatch_db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: aquawatch
      POSTGRES_USER: aquawatch
      POSTGRES_PASSWORD: aquawatch_dev
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

## Key Architectural Decisions

1. **Synchronous analysis** — CV runs during the request (< 2 seconds). No job queue needed for demo.
2. **Single process** — One uvicorn worker. No Celery, no Redis. Keep it simple.
3. **No image storage** — For demo, we process the image and store only the results. Image discarded after analysis. (Production would save to S3.)
4. **Stateless backend** — No sessions, no cache. Every request is independent.
5. **No WebSockets** — Dashboard polls or manually refreshes. Real-time updates are Phase 2.
