# AquaWatch - Implementation Roadmap (5-Day Sprint)

## Sprint Overview

**Goal**: Working demo showing the complete citizen report → analysis → dashboard flow.

**Must-Have for Demo Day**:
- Mobile app: Take photo → GPS → Submit
- Backend: Receive photo → CV analysis → Store → Return results
- Dashboard: Map with colored markers → Click for details

---

## Day 1: Backend Foundation + CV Pipeline

### Morning (4 hours)
- [ ] Set up project structure (all directories)
- [ ] `docker-compose.yml` — PostgreSQL + PostGIS container
- [ ] `requirements.txt` — FastAPI, uvicorn, SQLAlchemy, GeoAlchemy2, OpenCV, NumPy, python-multipart
- [ ] `app/config.py` — Environment variables (DB URL, etc.)
- [ ] `app/database.py` — SQLAlchemy engine, session, Base
- [ ] `app/models/` — water_body.py, report.py, risk_score.py (SQLAlchemy models)
- [ ] `app/main.py` — FastAPI app skeleton with CORS

### Afternoon (4 hours)
- [ ] `app/utils/forel_ule.py` — FU color lookup table (21 colors + names)
- [ ] `app/services/cv_analysis.py` — Full CV pipeline:
  - Pre-processing (decode, resize, ROI)
  - Forel-Ule analysis
  - Algae detection
  - Foam detection
  - Turbidity estimation
- [ ] `app/services/risk_scoring.py` — Composite score calculation
- [ ] Test CV pipeline with sample images (manual test)

### Day 1 Deliverable
✅ CV pipeline working independently (can analyze an image file and print results)
✅ Database tables created in Docker PostgreSQL
✅ FastAPI app starts without errors

---

## Day 2: API Endpoints + Seed Data

### Morning (4 hours)
- [ ] `app/services/water_body_matcher.py` — PostGIS proximity query
- [ ] `app/api/reports.py` — POST /analyze-water endpoint:
  - Accept multipart form (image + metadata)
  - Run CV analysis
  - Find/create water body
  - Store report
  - Return full analysis response
- [ ] `app/schemas/` — Pydantic schemas for request validation and response

### Afternoon (4 hours)
- [ ] `app/api/water_bodies.py` — GET endpoints:
  - GET /water-bodies (list with risk scores)
  - GET /water-bodies/{id} (detail)
  - GET /water-bodies/{id}/history
  - GET /water-bodies/{id}/reports
- [ ] `seed.py` — Seed script:
  - Insert 10 Bengaluru water bodies
  - Insert 3-5 fake reports per water body (varied scores)
  - Insert 4 weeks of historical risk scores
- [ ] GET /health endpoint
- [ ] Test all endpoints via Swagger UI (localhost:8000/docs)

### Day 2 Deliverable
✅ Complete working API — can submit a photo via Swagger and get analysis back
✅ Dashboard endpoints return seeded data
✅ All 10 water bodies in database with history

---

## Day 3: Dashboard + Flutter App Setup

### Morning (4 hours) — Dashboard
- [ ] `dashboard/index.html` — Page structure (map + side panel)
- [ ] `dashboard/style.css` — Layout, colors, responsive grid
- [ ] `dashboard/script.js` — Core functionality:
  - Initialize Leaflet map centered on Bengaluru
  - Fetch water bodies from API
  - Create color-coded circle markers
  - Click handler → populate side panel with details
  - Refresh button

### Afternoon (4 hours) — Flutter Setup
- [ ] `flutter create mobile` — Initialize Flutter project
- [ ] `pubspec.yaml` — Add dependencies (image_picker, geolocator, http/dio, permission_handler)
- [ ] `lib/main.dart` — App entry, routes, theme
- [ ] `lib/screens/home_screen.dart` — Landing screen with "Report" button
- [ ] `lib/screens/guidance_screen.dart` — Photo tips screen
- [ ] `lib/services/location_service.dart` — GPS permission + position
- [ ] Test: App opens, shows home screen, GPS permission works

### Day 3 Deliverable
✅ Dashboard shows map with 10 colored markers, click shows details
✅ Flutter app skeleton runs on emulator/device
✅ GPS permission working

---

## Day 4: Flutter App Complete + Integration

### Morning (4 hours) — Flutter Screens
- [ ] `lib/screens/camera_screen.dart` — image_picker camera capture
- [ ] `lib/screens/report_form_screen.dart` — Form with photo preview, dropdown, name field
- [ ] `lib/services/api_service.dart` — Multipart upload to backend
- [ ] `lib/screens/result_screen.dart` — Color-coded result card with breakdown
- [ ] `lib/widgets/` — contamination_dropdown, result_card, risk_indicator

### Afternoon (4 hours) — End-to-End Integration
- [ ] Test full flow: App → Camera → Form → Submit → Backend processes → Result shows
- [ ] Test: Dashboard shows the new report's impact on marker color
- [ ] Fix any issues with:
  - Image encoding/upload
  - GPS coordinate passing
  - Android cleartext traffic (HTTP in dev)
  - CORS issues
  - Response parsing in Flutter
- [ ] Add loading states (spinner during upload/analysis)

### Day 4 Deliverable
✅ Complete working flow: Mobile photo → Backend analysis → Result displayed
✅ Dashboard reflects new submissions
✅ No crashes in the happy path

---

## Day 5: Polish + Demo Prep

### Morning (4 hours) — Polish
- [ ] Dashboard: Add summary stats in header/footer
- [ ] Dashboard: Improve panel UI (bars, badges, clean typography)
- [ ] Mobile: Error handling (no GPS, no internet, server error)
- [ ] Mobile: Loading states and animations
- [ ] Backend: Ensure risk scores recalculate correctly with new reports
- [ ] Fix any bugs found during Day 4 testing

### Afternoon (4 hours) — Demo Prep
- [ ] Create `README.md` with setup instructions
- [ ] Write demo script (step-by-step what to show)
- [ ] Create `.env.example`
- [ ] Test full demo flow 3 times end-to-end
- [ ] Prepare 3-4 test photos (clean water, green water, foamy water, muddy water)
- [ ] Record backup video of demo (in case live demo fails)
- [ ] Ensure everything starts cleanly from scratch:
  - `docker-compose up -d`
  - `python seed.py`
  - `uvicorn app.main:app --reload`
  - Open dashboard
  - Launch Flutter app

### Day 5 Deliverable
✅ Polished, demo-ready application
✅ Clean startup process documented
✅ Test photos prepared
✅ Demo script ready

---

## Dependencies Between Days

```
Day 1 (Backend + CV) ──▶ Day 2 (API + Seed) ──▶ Day 3 (Dashboard + Flutter setup)
                                                         │
                                                         ▼
                                              Day 4 (Integration) ──▶ Day 5 (Polish)
```

- Day 3 Dashboard needs Day 2 API endpoints
- Day 3 Flutter needs Day 1 backend running
- Day 4 Integration needs everything from Days 1-3
- Day 5 is pure polish, no new features

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| CV analysis takes too long | Pre-resize images to 800px max, ~1-2s is acceptable |
| PostGIS query issues | Have a fallback: if no water body found, create one |
| Flutter camera issues on device | Use image_picker (reliable) not camera package |
| GPS not working in emulator | Set mock location in emulator settings |
| CORS errors | Already handled with allow_origins=["*"] |
| Demo day DB is empty | Seed script ensures data is always there |
| Live demo fails | Record backup video on Day 5 |

---

## What's NOT in the Demo

- Authentication / user accounts
- Satellite data integration (GEE)
- Email/SMS alerts
- Offline queue
- Multiple photos per report
- Admin panel
- Real-time WebSocket updates
- Production deployment
- Automated tests

These are all Phase 2 features.
