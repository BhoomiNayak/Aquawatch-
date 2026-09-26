"""
Satellite corroboration service.

Exposes the latest Sentinel-2 NDCI (chlorophyll / eutrophication proxy) status
for a named water body, computed offline by
`scripts/sentinel_ndci_timeseries.py` and cached in
`reports/sentinel_ndci_monthly.csv`.

Design decisions (deliberate)
-----------------------------
- This is an INDEPENDENT, complementary physical-corroboration layer. It is NOT
  probabilistically fused with the ground-image classifier (that classifier was
  measured at ROC-AUC 0.49 out-of-distribution; blending a chance-level signal
  would only add noise). The API surfaces satellite status alongside the
  report, it does not average the two.
- Anomaly scoring is RELATIVE, never absolute: a lake's latest NDCI is compared
  against its OWN historical 75th percentile and against the clean-reference
  baseline. No mg/m^3 chlorophyll thresholds are claimed, because there is no
  in-situ calibration.
- Reads a precomputed CSV rather than calling Earth Engine in the request path
  (EE calls need auth + are too slow for an API request). Re-run the offline
  script to refresh the cache.

Two tiers
---------
1. CACHED (fast): pre-defined lakes with an offline NDCI time-series ->
   `get_lake_satellite_metrics(name)`. Gives self-anomaly + clean-baseline.
2. ON-DEMAND (slow, best-effort): arbitrary user GPS points ->
   `get_metrics_for_point(lat, lon)`. Buffers the point, pulls the latest
   cloud-free Sentinel-2 scene live from Earth Engine, gates on a minimum
   open-water pixel count, and compares NDCI to the fixed clean baseline.
   No per-point history, so no self-anomaly.

Public API
----------
    get_lake_satellite_metrics(water_body_name) -> dict          (cached tier)
    get_metrics_for_point(lat, lon) -> dict                      (on-demand tier)
    get_satellite_status_for_water_body(db, water_body) -> dict  (matcher glue)
"""

from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MONTHLY_CSV = os.path.join(BASE, "reports", "sentinel_ndci_monthly.csv")

# clean-reference categories used to derive a "clean baseline" NDCI
CLEAN_CATEGORIES = {"clean_reference"}

# ── On-demand (Earth Engine) configuration ────────────────────────────────
KEY_PATH = os.path.join(BASE, "keys", "gee_service_account.json")
# SCL classes to mask out of Sentinel-2 L2A (saturated, shadow, cloud, cirrus, snow)
SCL_MASK_CLASSES = [1, 3, 8, 9, 10, 11]
S2_SCALE_M = 20                       # B5 (red-edge) native resolution
DEFAULT_CLEAN_BASELINE = 0.015        # fixed clean-reference NDCI (from clean-ref p75)
POINT_BUFFER_M = 150                  # base buffer; escalates if no open water found
BUFFER_ESCALATION_M = [150, 300, 500]  # bank points / weed-choked shores need wider search
LOOKBACK_DAYS = 180                   # monsoon-tolerant window for the median composite
SCENE_CLOUD_CEILING = 80              # skip fully-clouded scenes; per-pixel SCL does the rest
MIN_WATER_PX = 5

_lock = threading.Lock()
_cache = None            # {"mtime": float, "by_lake": {...}, "clean_baseline_p75": float|None}

# lazy Earth Engine handle (kept module-level so we init at most once)
_ee = None
_ee_error = None


# ── Loading / caching ─────────────────────────────────────────────────────
def _normalize(name: str) -> str:
    """Loose name key: lowercase and drop generic 'lake'/'reservoir' tails.

    Note we deliberately keep 'sagar'/'tank' since they are part of proper
    names (e.g. 'Hussain Sagar') rather than generic descriptors.
    """
    n = (name or "").strip().lower()
    n = n.replace("reservoir", "").replace("lake", "")
    return " ".join(n.split()).strip()


def _load(force: bool = False):
    """Load and index the monthly CSV, reloading if the file changed on disk."""
    global _cache
    with _lock:
        if not os.path.exists(MONTHLY_CSV):
            _cache = {"mtime": 0, "by_lake": {}, "clean_baseline_p75": None,
                      "available": False}
            return _cache

        mtime = os.path.getmtime(MONTHLY_CSV)
        if _cache and not force and _cache.get("mtime") == mtime:
            return _cache

        by_lake: dict[str, dict] = {}
        with open(MONTHLY_CSV, newline="") as f:
            for row in csv.DictReader(f):
                lake = row["lake"]
                val = row.get("ndci_mean", "")
                if val in ("", "None", None):
                    continue
                try:
                    ndci = float(val)
                except ValueError:
                    continue
                rec = by_lake.setdefault(lake, {
                    "lake": lake,
                    "category": row.get("category", "unknown"),
                    "series": [],   # list of (date, ndci)
                })
                rec["series"].append((row["date"], ndci))

        # finalize per-lake stats
        clean_p75s = []
        for lake, rec in by_lake.items():
            rec["series"].sort(key=lambda t: t[0])
            vals = [v for _, v in rec["series"]]
            rec["n_months"] = len(vals)
            rec["ndci_latest"] = vals[-1]
            rec["latest_date"] = rec["series"][-1][0]
            rec["ndci_p75"] = _percentile(vals, 75)
            rec["ndci_median"] = _percentile(vals, 50)
            if rec["category"] in CLEAN_CATEGORIES:
                clean_p75s.append(rec["ndci_p75"])

        clean_baseline = (sum(clean_p75s) / len(clean_p75s)) if clean_p75s else None
        _cache = {"mtime": mtime, "by_lake": by_lake,
                  "clean_baseline_p75": clean_baseline, "available": True}
        return _cache


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (no numpy dependency in request path)."""
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


# ── Public API ────────────────────────────────────────────────────────────
def get_lake_satellite_metrics(water_body_name: str) -> dict:
    """
    Latest Sentinel-2 NDCI status for a named water body.

    Returns a dict with:
        available            bool  — is there cached satellite data for this lake
        lake                 str
        category             str   — polluted / moderate / clean_reference
        ndci_latest          float
        latest_date          str   (YYYY-MM)
        ndci_p75             float — this lake's own historical 75th percentile
        self_anomaly         bool  — latest > own p75  (unusually high for itself)
        clean_baseline_p75   float|None — mean p75 of clean-reference lakes
        vs_clean_ratio       float|None — latest / clean baseline
        exceeds_clean_baseline bool|None — latest > clean baseline
        water_surface_status str   — "water_detected" / "no_recent_water" / "unknown"
        n_months             int
        source               str
        note                 str
    """
    cache = _load()
    result = {
        "available": False,
        "lake": water_body_name,
        "category": None,
        "ndci_latest": None,
        "latest_date": None,
        "ndci_p75": None,
        "self_anomaly": None,
        "clean_baseline_p75": cache.get("clean_baseline_p75"),
        "vs_clean_ratio": None,
        "exceeds_clean_baseline": None,
        "water_surface_status": "unknown",
        "n_months": 0,
        "source": "Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED) NDCI, cached",
        "note": "Relative anomaly scoring; not calibrated to absolute chlorophyll.",
    }

    if not cache.get("available"):
        result["note"] = ("No cached satellite data. Run "
                          "scripts/sentinel_ndci_timeseries.py to generate "
                          "reports/sentinel_ndci_monthly.csv.")
        return result

    # match by exact then normalized name
    by_lake = cache["by_lake"]
    rec = by_lake.get(water_body_name)
    if rec is None:
        target = _normalize(water_body_name)
        for lake, r in by_lake.items():
            if _normalize(lake) == target:
                rec = r
                break
    if rec is None:
        result["note"] = (f"'{water_body_name}' is not a tracked satellite target. "
                          f"Tracked: {sorted(by_lake.keys())}")
        return result

    latest = rec["ndci_latest"]
    p75 = rec["ndci_p75"]
    clean_base = cache.get("clean_baseline_p75")

    result.update({
        "available": True,
        "lake": rec["lake"],
        "category": rec["category"],
        "ndci_latest": round(latest, 4),
        "latest_date": rec["latest_date"],
        "ndci_p75": round(p75, 4),
        "self_anomaly": bool(latest > p75),
        "n_months": rec["n_months"],
        "water_surface_status": "water_detected",  # series only holds water-masked months
    })
    if clean_base is not None:
        result["clean_baseline_p75"] = round(clean_base, 4)
        # guard divide-by-zero / near-zero baselines
        if abs(clean_base) > 1e-6:
            result["vs_clean_ratio"] = round(latest / clean_base, 3)
        result["exceeds_clean_baseline"] = bool(latest > clean_base)

    return result


def _clean_baseline() -> float:
    """Clean-reference NDCI baseline: data-derived if available, else the fixed default."""
    b = _load().get("clean_baseline_p75")
    return float(b) if b is not None else DEFAULT_CLEAN_BASELINE


# ── On-demand tier: live Earth Engine query for an arbitrary GPS point ─────
def _resolve_key_path():
    """Locate the GEE service-account key.

    Prefers the canonical `keys/gee_service_account.json`, but falls back to any
    `keys/*.json` that is a service-account key (so a freshly downloaded
    `water-quality-sentinel-xxxx.json` works without renaming).
    """
    if os.path.exists(KEY_PATH):
        return KEY_PATH
    keys_dir = os.path.dirname(KEY_PATH)
    if os.path.isdir(keys_dir):
        import glob
        import json
        for p in sorted(glob.glob(os.path.join(keys_dir, "*.json"))):
            try:
                with open(p) as f:
                    if json.load(f).get("type") == "service_account":
                        return p
            except Exception:
                continue
    return None


def _init_ee():
    """Lazily initialise Earth Engine (service account, else default creds).

    Returns the `ee` module on success, or None (with _ee_error set) on failure.
    Import and init are deferred so the API imports fine without earthengine-api.
    """
    global _ee, _ee_error
    if _ee is not None:
        return _ee
    if _ee_error is not None:
        return None
    try:
        import ee  # type: ignore
    except ImportError:
        _ee_error = "earthengine-api not installed"
        return None
    try:
        key_path = _resolve_key_path()
        if key_path:
            import json
            with open(key_path) as f:
                sa = json.load(f)
            creds = ee.ServiceAccountCredentials(sa.get("client_email"), key_path)
            # newer EE requires an explicit project; take it from the key.
            ee.Initialize(creds, project=sa.get("project_id"))
        else:
            # fallback: interactive/default creds (local testing only).
            # newer EE needs a project id -> allow EE_PROJECT_ID env override.
            proj = os.environ.get("EE_PROJECT_ID")
            ee.Initialize(project=proj) if proj else ee.Initialize()
        _ee = ee
        return ee
    except Exception as exc:  # noqa: BLE001 - report any init failure upward
        _ee_error = f"ee init failed: {exc}"
        return None


def _composite_stats(ee, region, end, days):
    """SCL-masked median composite over [end-days, end]; return (n_scenes, stats).

    Uses per-pixel cloud masking (not whole-scene cloud-free filtering) so that
    clear pixels from partly-cloudy scenes still contribute — essential for
    monsoon regions where no single scene is <20% cloud for months.
    """
    start = end.advance(-days, "day")
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(region)
           .filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", SCENE_CLOUD_CEILING)))
    n = col.size().getInfo()
    if n == 0:
        return 0, None

    def scl_mask(img):
        keep = img.select("SCL").remap(SCL_MASK_CLASSES,
                                       [0] * len(SCL_MASK_CLASSES), 1)
        return img.updateMask(keep)

    comp = col.map(scl_mask).median()
    ndwi = comp.normalizedDifference(["B3", "B8"])          # water index
    water = ndwi.gt(0)
    ndci = (comp.normalizedDifference(["B5", "B4"])          # chlorophyll proxy
            .updateMask(water).rename("ndci"))
    stats = ndci.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.count(), None, True),
        geometry=region, scale=S2_SCALE_M, maxPixels=1e9, bestEffort=True,
    ).getInfo()
    return n, stats


def get_metrics_for_point(lat: float, lon: float,
                          buffer_m: int = POINT_BUFFER_M,
                          lookback_days: int = LOOKBACK_DAYS,
                          min_water_px: int = MIN_WATER_PX) -> dict:
    """
    Best-effort satellite corroboration for an arbitrary GPS point.

    Buffers the point, builds a per-pixel-cloud-masked median composite of
    Sentinel-2 L2A over the lookback window, water-masks via NDWI, and — only if
    enough open water pixels are present — returns the spatial-mean NDCI
    compared to the fixed clean-reference baseline. If the primary window has no
    usable water pixels, it retries once over an extended window.

    Returns (success):
        {available: True, live_ndci, exceeds_clean_baseline, water_pixel_count,
         clean_baseline, window_days, scenes_used, buffer_m, source, note}
    Returns (graceful failure):
        {available: False, reason: "ee_unavailable" | "cloud_cover_or_timeout"
                                    | "sub_pixel_or_no_water", ...}

    Note: deliberately uses a median composite (not a single 'latest cloud-free
    scene'). In monsoon India no single scene is <20% cloud for months, so the
    single-scene approach returns 'unavailable' most of the year; per-pixel
    masking + compositing recovers usable water observations.
    """
    ee = _init_ee()
    if ee is None:
        return {"available": False, "reason": "ee_unavailable", "detail": _ee_error}

    try:
        import datetime as _dt
        point = ee.Geometry.Point([lon, lat])
        end = ee.Date(_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"))

        # Escalate the buffer: bank points and weed-choked shorelines have no
        # open water within 150 m, so widen the search until water appears.
        buffers = [buffer_m] + [b for b in BUFFER_ESCALATION_M if b > buffer_m]

        n_scenes = 0
        for b in buffers:
            region = point.buffer(b)
            n_scenes, stats = _composite_stats(ee, region, end, lookback_days)
            if stats is None:
                continue
            px = int(stats.get("ndci_count") or 0)
            mean_ndci = stats.get("ndci_mean")
            if px >= min_water_px and mean_ndci is not None:
                baseline = _clean_baseline()
                # Spatial confidence: water found at the tight base buffer is a
                # confident on-spot reading; water only found after widening the
                # search is "nearby water", and may be a different/adjacent body.
                if b <= buffer_m:
                    confidence = "high"
                elif b <= 300:
                    confidence = "medium"
                else:
                    confidence = "low"
                return {
                    "available": True,
                    "live_ndci": round(float(mean_ndci), 4),
                    "exceeds_clean_baseline": bool(mean_ndci > baseline),
                    "clean_baseline": round(baseline, 4),
                    "water_pixel_count": px,
                    "buffer_m": b,
                    "spatial_confidence": confidence,
                    "window_days": lookback_days,
                    "scenes_used": n_scenes,
                    "source": f"Sentinel-2 L2A on-demand median composite (<{lookback_days}d)",
                    "note": "Relative to clean-reference baseline; not calibrated "
                            "to absolute chlorophyll. Buffer averages the water "
                            "surface near the point, not the exact photographed spot. "
                            "spatial_confidence=low means water was only found by "
                            "widening the search and may be an adjacent water body.",
                }

        # No usable water pixels at any buffer.
        if n_scenes == 0:
            return {"available": False, "reason": "cloud_cover_or_timeout",
                    "detail": "no Sentinel-2 scenes in lookback window"}
        return {"available": False, "reason": "sub_pixel_or_no_water",
                "water_pixel_count": 0, "scenes_used": n_scenes,
                "detail": f"scenes existed but no open water within {buffers[-1]} m"}
    except Exception as exc:  # noqa: BLE001 - any EE/runtime error is a graceful miss
        return {"available": False, "reason": "cloud_cover_or_timeout", "detail": str(exc)}


def _corroboration(metrics: dict) -> str:
    """Map a metrics dict (cached or on-demand) to a compact verdict."""
    if not metrics.get("available"):
        return "unavailable"
    exceeds_clean = metrics.get("exceeds_clean_baseline")
    self_anom = metrics.get("self_anomaly")
    if exceeds_clean and self_anom:
        return "elevated"           # high vs peers AND vs own history (cached tier only)
    if exceeds_clean or self_anom:
        return "watch"              # one signal elevated
    return "nominal"


def get_satellite_status_for_water_body(db, water_body) -> dict:
    """
    Glue for the report pipeline. Given a matched WaterBody:

      1. Try the fast CACHED tier by name (pre-defined lakes).
      2. If that misses and the body has coordinates, fall back to the
         ON-DEMAND point engine (live Earth Engine query at its lat/lon).

    Always returns a dict carrying `corroboration`, `mode`, and `checked_at`.
    """
    name = getattr(water_body, "name", None)
    metrics = get_lake_satellite_metrics(name) if name else {"available": False}
    mode = "cached_lake"

    if not metrics.get("available"):
        lat = getattr(water_body, "latitude", None)
        lon = getattr(water_body, "longitude", None)
        if lat is not None and lon is not None:
            metrics = get_metrics_for_point(lat, lon)
            mode = "on_demand_point"

    metrics["mode"] = mode
    metrics["corroboration"] = _corroboration(metrics)
    metrics["checked_at"] = datetime.now(timezone.utc).isoformat()
    return metrics
