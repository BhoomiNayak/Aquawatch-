# AquaWatch - Database Schema

## Database: PostgreSQL 15 + PostGIS 3.3

Connection string (dev):
```
postgresql://aquawatch:aquawatch_dev@localhost:5432/aquawatch
```

---

## Tables

### 1. water_bodies

Stores all monitored water bodies with geographic location.

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE water_bodies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    location        GEOMETRY(Point, 4326) NOT NULL,  -- PostGIS point (SRID 4326 = WGS84)
    type            VARCHAR(50) DEFAULT 'lake',       -- lake, pond, tank, wetland, reservoir
    city            VARCHAR(100) DEFAULT 'Bengaluru',
    state           VARCHAR(100) DEFAULT 'Karnataka',
    
    -- Current risk (denormalized for fast dashboard queries)
    current_risk_score  DOUBLE PRECISION DEFAULT 0.0,   -- 0-100
    current_risk_level  VARCHAR(20) DEFAULT 'low',      -- low, moderate, high
    total_reports       INTEGER DEFAULT 0,
    
    -- Timestamps
    last_report_at  TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Spatial index for proximity queries (ST_DWithin)
CREATE INDEX idx_water_bodies_location ON water_bodies USING GIST(location);

-- Risk level filter
CREATE INDEX idx_water_bodies_risk ON water_bodies(current_risk_level);
```

### 2. reports

Individual citizen reports with CV analysis results.

```sql
CREATE TABLE reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    water_body_id       UUID NOT NULL REFERENCES water_bodies(id) ON DELETE CASCADE,
    
    -- Location (where photo was taken - may differ slightly from water body center)
    latitude            DOUBLE PRECISION NOT NULL,
    longitude           DOUBLE PRECISION NOT NULL,
    location            GEOMETRY(Point, 4326) NOT NULL,
    
    -- User input
    contamination_type  VARCHAR(50) NOT NULL,
    reporter_name       VARCHAR(100),
    notes               TEXT,
    
    -- CV Analysis Results (stored for history)
    forel_ule_index     INTEGER,              -- 1-21
    forel_ule_color     VARCHAR(50),          -- e.g., "Greenish Brown"
    algae_percentage    DOUBLE PRECISION,      -- 0-100
    foam_detected       BOOLEAN DEFAULT FALSE,
    foam_coverage_pct   DOUBLE PRECISION,      -- 0-100
    turbidity_score     DOUBLE PRECISION,      -- 0-100 (higher = clearer)
    
    -- Composite score
    composite_score     DOUBLE PRECISION NOT NULL,  -- 0-100
    risk_level          VARCHAR(20) NOT NULL,       -- low, moderate, high
    
    -- Timestamps
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Lookup by water body (most common query)
CREATE INDEX idx_reports_water_body ON reports(water_body_id, created_at DESC);

-- Time-based queries (last 7 days for risk calculation)
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);

-- Spatial index (for finding nearest water body during submission)
CREATE INDEX idx_reports_location ON reports USING GIST(location);
```

### 3. risk_scores

Historical risk score snapshots — one record per water body per recalculation.

```sql
CREATE TABLE risk_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    water_body_id   UUID NOT NULL REFERENCES water_bodies(id) ON DELETE CASCADE,
    
    -- Score
    risk_score      DOUBLE PRECISION NOT NULL,  -- 0-100
    risk_level      VARCHAR(20) NOT NULL,       -- low, moderate, high
    
    -- Component averages (for the scoring window)
    avg_algae_pct       DOUBLE PRECISION,
    avg_foam_coverage   DOUBLE PRECISION,
    avg_turbidity       DOUBLE PRECISION,
    report_count        INTEGER,
    
    -- Time window this score covers
    window_start    TIMESTAMP WITH TIME ZONE,
    window_end      TIMESTAMP WITH TIME ZONE,
    
    -- Timestamp
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- History lookup (for trend charts)
CREATE INDEX idx_risk_scores_history ON risk_scores(water_body_id, created_at DESC);
```

---

## Relationships

```
water_bodies (1) ──── (N) reports
water_bodies (1) ──── (N) risk_scores
```

---

## Seed Data

The `seed.py` script will:

1. Insert 10 Bengaluru water bodies with coordinates
2. Insert 3-5 fake reports per water body with varied analysis results
3. Insert 4 weeks of historical risk scores for trend demo

### Seed Water Bodies

```python
SEED_WATER_BODIES = [
    {"name": "Ulsoor Lake", "lat": 12.9825, "lng": 77.6200, "type": "lake"},
    {"name": "Sankey Tank", "lat": 13.0080, "lng": 77.5730, "type": "tank"},
    {"name": "Bellandur Lake", "lat": 12.9373, "lng": 77.6784, "type": "lake"},
    {"name": "Yediyur Lake", "lat": 12.9380, "lng": 77.5700, "type": "lake"},
    {"name": "Puttenahalli Lake", "lat": 12.8900, "lng": 77.5880, "type": "lake"},
    {"name": "Agara Lake", "lat": 12.9250, "lng": 77.6380, "type": "lake"},
    {"name": "Lalbagh Lake", "lat": 12.9507, "lng": 77.5848, "type": "lake"},
    {"name": "Kaikondrahalli Lake", "lat": 12.9100, "lng": 77.6740, "type": "lake"},
    {"name": "Jakkur Lake", "lat": 13.0700, "lng": 77.6100, "type": "lake"},
    {"name": "Hennur Lake", "lat": 13.0450, "lng": 77.6350, "type": "lake"},
]
```

### Seed Risk Profiles (for realistic demo)

| Water Body | Risk Level | Rationale |
|-----------|-----------|-----------|
| Bellandur Lake | High | Famous for pollution, foam |
| Ulsoor Lake | Moderate | Central, mixed quality |
| Sankey Tank | Low | Well-maintained |
| Yediyur Lake | Low | Small, clean |
| Puttenahalli Lake | Low | Community managed |
| Agara Lake | Moderate | Some algae |
| Lalbagh Lake | Low | Protected area |
| Kaikondrahalli Lake | Low | Restored wetland |
| Jakkur Lake | Moderate | Treated sewage inlet |
| Hennur Lake | Moderate | Urban runoff |

---

## SQLAlchemy Model Notes

- Use `GeoAlchemy2` for PostGIS geometry columns
- `location` column: `Geometry('POINT', srid=4326)`
- Auto-generate UUID with `server_default=text("gen_random_uuid()")`
- Use `func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)` when inserting points
- Use `func.ST_DWithin()` for proximity queries (geography cast for meter-based distance)

---

## Migration Strategy

For the demo, use a simple approach:
1. `database.py` creates tables on startup with `Base.metadata.create_all()`
2. `seed.py` is run manually once after DB is up
3. No Alembic for demo (add post-demo for production)

### Startup sequence:
```bash
docker-compose up -d          # Start PostgreSQL
python -m app.database        # Create tables (or auto on first request)
python seed.py                # Populate with demo data
uvicorn app.main:app --reload # Start server
```
