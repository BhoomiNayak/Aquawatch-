# AquaWatch - Tech Stack

## Backend

- **Language**: Python 3.10+
- **Framework**: FastAPI 0.104.x with Uvicorn ASGI server
- **Database**: PostgreSQL with PostGIS extension (spatial queries)
- **ORM**: SQLAlchemy 2.0 with GeoAlchemy2 for spatial column types
- **Image Processing**: OpenCV (cv2) 4.8.x + NumPy 1.26.x
- **Configuration**: pydantic-settings (env-based config via `.env` files)
- **Migrations**: Alembic (available but tables are auto-created on startup)

## Frontend (Dashboard)

- **Type**: Static HTML/CSS/JS (no build step, no framework)
- **Map Library**: Leaflet.js 1.9.4 (loaded from CDN)
- **API Communication**: Vanilla fetch() to backend REST API

## API Design

- REST API versioned at `/api/v1`
- Multipart/form-data for image uploads (`POST /api/v1/analyze-water`)
- JSON responses for all endpoints
- CORS enabled (configured via environment variable)

## Database Details

- PostGIS `Geometry("POINT", srid=4326)` columns for spatial lookups
- `ST_DWithin` and `ST_Distance` for proximity matching (geography cast for meters)
- UUIDs (string-based, 36 chars) as primary keys

## Common Commands

```bash
# Install backend dependencies
pip install -r backend/requirements.txt

# Run the backend API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# (run from backend/ directory)

# Seed database with sample water bodies
python backend/seed.py

# Run CV pipeline tests on real images
python backend/test_real_images.py

# Test the full API flow
python backend/test_api_flow.py

# Calibrate risk thresholds
python backend/calibrate_thresholds.py
```

## Environment Variables

Configured via `backend/.env` (see `backend/.env.example`):
- `DATABASE_URL` - PostgreSQL connection string (must have PostGIS)
- `HOST`, `PORT`, `DEBUG` - server settings
- `CORS_ORIGINS` - allowed origins
- `MAX_IMAGE_SIZE_MB` - upload size limit
- `IMAGE_MAX_DIMENSION` - resize target for CV processing

## Key Libraries

| Library | Purpose |
|---------|---------|
| fastapi | Web framework and API routing |
| sqlalchemy + geoalchemy2 | ORM with spatial support |
| psycopg2-binary | PostgreSQL driver |
| opencv-python | Computer vision analysis |
| numpy | Numerical operations for image processing |
| pydantic-settings | Typed configuration from environment |
| python-multipart | Multipart form data handling |
