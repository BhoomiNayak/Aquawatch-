# AquaWatch - API Design

## Base URL
```
http://localhost:8000/api/v1
```

## Endpoints Overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /analyze-water | Submit photo for analysis, get results |
| GET | /water-bodies | List all water bodies with current risk |
| GET | /water-bodies/{id} | Single water body detail |
| GET | /water-bodies/{id}/history | Risk score history for trends |
| GET | /water-bodies/{id}/reports | Individual reports for a water body |
| GET | /health | Health check |

---

## POST /analyze-water

The primary endpoint. Accepts a photo + metadata, runs CV analysis, stores results, returns breakdown.

### Request: `multipart/form-data`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| image | File (JPEG/PNG) | Yes | Max 10MB |
| latitude | float | Yes | -90 to 90 |
| longitude | float | Yes | -180 to 180 |
| contamination_type | string | Yes | Enum (see below) |
| reporter_name | string | No | Max 100 chars |
| notes | string | No | Max 500 chars |

### Contamination Type Enum
```
industrial_discharge | sewage | algal_bloom | solid_waste | 
agricultural_runoff | fish_kill | foam | oil_spill | others
```

### Response (201 Created)
```json
{
  "report_id": "uuid-here",
  "water_body": {
    "id": "uuid-water-body",
    "name": "Bellandur Lake",
    "distance_meters": 120.5
  },
  "analysis": {
    "forel_ule_index": 14,
    "forel_ule_color": "Greenish Brown",
    "algae_percentage": 35.2,
    "foam_detected": true,
    "foam_coverage_percentage": 12.5,
    "turbidity_score": 45.0,
    "clarity_description": "Moderately Turbid"
  },
  "risk": {
    "composite_score": 68.7,
    "risk_level": "high",
    "breakdown": {
      "algae_component": 14.08,
      "foam_component": 3.75,
      "turbidity_component": 16.5
    }
  },
  "created_at": "2026-08-10T14:30:00Z"
}
```

### Response (422 Validation Error)
```json
{
  "detail": [
    {
      "loc": ["body", "latitude"],
      "msg": "ensure this value is greater than or equal to -90",
      "type": "value_error"
    }
  ]
}
```

### Response (400 Bad Request - Image Issues)
```json
{
  "detail": "Image could not be decoded. Please upload a valid JPEG or PNG file."
}
```

---

## GET /water-bodies

Return all monitored water bodies with their current risk level.

### Query Parameters
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| risk_level | string | null | Filter: low, moderate, high |
| limit | int | 50 | Max results |
| offset | int | 0 | Pagination offset |

### Response (200 OK)
```json
{
  "count": 10,
  "water_bodies": [
    {
      "id": "uuid-1",
      "name": "Bellandur Lake",
      "latitude": 12.9373,
      "longitude": 77.6784,
      "type": "lake",
      "risk_level": "high",
      "risk_score": 72.5,
      "total_reports": 23,
      "reports_last_7_days": 8,
      "last_report_at": "2026-08-10T12:00:00Z"
    },
    {
      "id": "uuid-2",
      "name": "Sankey Tank",
      "latitude": 13.0080,
      "longitude": 77.5730,
      "type": "tank",
      "risk_level": "low",
      "risk_score": 15.3,
      "total_reports": 5,
      "reports_last_7_days": 1,
      "last_report_at": "2026-08-08T09:15:00Z"
    }
  ]
}
```

---

## GET /water-bodies/{id}

Detailed information about a single water body including latest analysis.

### Response (200 OK)
```json
{
  "id": "uuid-1",
  "name": "Bellandur Lake",
  "latitude": 12.9373,
  "longitude": 77.6784,
  "type": "lake",
  "city": "Bengaluru",
  "risk_level": "high",
  "risk_score": 72.5,
  "total_reports": 23,
  "reports_last_7_days": 8,
  "latest_analysis": {
    "forel_ule_index": 14,
    "algae_percentage": 35.2,
    "foam_detected": true,
    "turbidity_score": 45.0
  },
  "contamination_breakdown": {
    "industrial_discharge": 8,
    "sewage": 6,
    "algal_bloom": 5,
    "solid_waste": 3,
    "others": 1
  },
  "last_report_at": "2026-08-10T12:00:00Z",
  "created_at": "2026-08-06T00:00:00Z"
}
```

### Response (404)
```json
{
  "detail": "Water body not found"
}
```

---

## GET /water-bodies/{id}/history

Weekly risk score history for trend visualization.

### Query Parameters
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| days | int | 30 | Number of days of history |

### Response (200 OK)
```json
{
  "water_body_id": "uuid-1",
  "water_body_name": "Bellandur Lake",
  "history": [
    {
      "date": "2026-08-10",
      "risk_score": 72.5,
      "risk_level": "high",
      "report_count": 8,
      "avg_algae": 35.2,
      "avg_turbidity": 45.0
    },
    {
      "date": "2026-08-03",
      "risk_score": 58.1,
      "risk_level": "moderate",
      "report_count": 6,
      "avg_algae": 28.0,
      "avg_turbidity": 52.0
    }
  ]
}
```

---

## GET /water-bodies/{id}/reports

Individual reports submitted for a water body.

### Query Parameters
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | Max reports |
| offset | int | 0 | Pagination offset |

### Response (200 OK)
```json
{
  "water_body_id": "uuid-1",
  "total": 23,
  "reports": [
    {
      "id": "report-uuid",
      "contamination_type": "industrial_discharge",
      "reporter_name": "Rahul S",
      "notes": "Foam visible on surface",
      "analysis": {
        "forel_ule_index": 16,
        "algae_percentage": 42.1,
        "foam_detected": true,
        "foam_coverage_percentage": 18.3,
        "turbidity_score": 38.0,
        "composite_score": 71.2,
        "risk_level": "high"
      },
      "latitude": 12.9375,
      "longitude": 77.6780,
      "created_at": "2026-08-10T14:30:00Z"
    }
  ]
}
```

---

## GET /health

### Response (200 OK)
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0",
  "opencv_version": "4.8.0"
}
```

---

## Error Response Format

All errors follow this structure:
```json
{
  "detail": "Human-readable error message"
}
```

HTTP status codes used:
- 200: Success (GET)
- 201: Created (POST)
- 400: Bad request (invalid image, etc.)
- 404: Not found
- 422: Validation error (Pydantic)
- 500: Internal server error

---

## CORS Configuration (Demo)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Notes

- **No authentication** — Open endpoints for demo
- **File upload limit** — 10MB max image size
- **Processing time** — CV analysis takes ~1-2 seconds per image
- **No pagination on map** — All water bodies returned at once (only ~10 for demo)
- **Image not stored** — Processed and discarded; only analysis results saved
