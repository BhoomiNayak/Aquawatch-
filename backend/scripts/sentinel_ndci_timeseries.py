"""
sentinel_ndci_timeseries.py
===========================
Sentinel-2 NDCI (chlorophyll / eutrophication proxy) monthly time-series for
the AquaWatch target water bodies, via Google Earth Engine.

What it does
------------
For each lake polygon in datasets/target_lakes.geojson:
  1. Filters COPERNICUS/S2_SR_HARMONIZED (Level-2A surface reflectance),
     CLOUDY_PIXEL_PERCENTAGE < 20, and SCL-based per-pixel cloud/shadow masking.
  2. Builds a monthly median composite (2021 -> present).
  3. Water mask:  NDWI = (B3 - B8)/(B3 + B8) > 0   (keeps water pixels only).
  4. NDCI = (B5 - B4)/(B5 + B4)  averaged over masked water pixels.
  5. Emits a monthly mean NDCI series per lake.

Outputs
-------
  reports/sentinel_ndci_monthly.csv   full monthly series (consumed by satellite.py)
  reports/sentinel_lake_summary.csv   per-lake summary (mean/median/p75/latest)
  reports/plots/sentinel_ndci_timeseries.png   polluted vs clean-reference plot

Scientific framing
-------------------
No in-situ chlorophyll measurements exist, so NDCI is reported in RELATIVE terms
(polluted lakes vs clean-reference controls, and each lake vs its own history).
Absolute mg/m^3 chlorophyll thresholds are intentionally NOT claimed.

Auth / setup
------------
  pip install earthengine-api pandas matplotlib
  earthengine authenticate          # one-time, opens browser
Provide your Google Cloud project id via --project or the EE_PROJECT_ID env var:
  python scripts/sentinel_ndci_timeseries.py --project my-gee-project-id

Usage
-----
  cd backend
  python scripts/sentinel_ndci_timeseries.py --project <PROJECT_ID>
  python scripts/sentinel_ndci_timeseries.py --project <PROJECT_ID> --start 2021-01-01
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import logging

os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

BASE = os.path.dirname(os.path.dirname(__file__))
GEOJSON = os.path.join(BASE, "datasets", "target_lakes.geojson")
OUT_MONTHLY = os.path.join(BASE, "reports", "sentinel_ndci_monthly.csv")
OUT_SUMMARY = os.path.join(BASE, "reports", "sentinel_lake_summary.csv")
OUT_PLOT = os.path.join(BASE, "reports", "plots", "sentinel_ndci_timeseries.png")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("sentinel")

# SCL classes to mask out of Sentinel-2 L2A (cloud, shadow, cirrus, snow, saturated).
#  1=saturated 3=cloud-shadow 8=cloud-medium 9=cloud-high 10=cirrus 11=snow/ice
SCL_MASK_CLASSES = [1, 3, 8, 9, 10, 11]
S2_SCALE_M = 20  # B5 (red-edge) native resolution


# ── GEE init ────────────────────────────────────────────────────────────────
def init_ee(project: str):
    import ee
    try:
        ee.Initialize(project=project)
    except Exception:
        log.info("ee.Initialize failed; attempting ee.Authenticate() ...")
        ee.Authenticate()
        ee.Initialize(project=project)
    log.info(f"Earth Engine initialised (project={project})")
    return ee


# ── Per-lake monthly NDCI (server-side) ──────────────────────────────────────
def build_monthly_fc(ee, geom, name, start_date, n_months):
    """Return an ee.FeatureCollection of monthly {date, ndci_mean, water_px, n_scenes}."""
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(geom)
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)))

    def mask_scl(img):
        scl = img.select("SCL")
        keep = scl.remap(SCL_MASK_CLASSES, [0] * len(SCL_MASK_CLASSES), 1)
        return img.updateMask(keep)

    s2 = s2.map(mask_scl)
    start = ee.Date(start_date)

    def per_month(m):
        m = ee.Number(m)
        mstart = start.advance(m, "month")
        mend = mstart.advance(1, "month")
        col = s2.filterDate(mstart, mend)
        n = col.size()

        def compute():
            comp = col.median()
            ndwi = comp.normalizedDifference(["B3", "B8"])        # water index
            ndci = comp.normalizedDifference(["B5", "B4"])        # chlorophyll proxy
            water = ndwi.gt(0)
            ndci_w = ndci.updateMask(water)
            stats = ndci_w.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), None, True),
                geometry=geom, scale=S2_SCALE_M, maxPixels=1e9, bestEffort=True)
            return ee.Feature(None, {
                "lake": name,
                "date": mstart.format("YYYY-MM"),
                "ndci_mean": stats.get("nd_mean"),
                "water_px": stats.get("nd_count"),
                "n_scenes": n,
            })

        empty = ee.Feature(None, {
            "lake": name, "date": mstart.format("YYYY-MM"),
            "ndci_mean": None, "water_px": 0, "n_scenes": n,
        })
        return ee.Feature(ee.Algorithms.If(n.gt(0), compute(), empty))

    months = ee.List.sequence(0, n_months - 1)
    return ee.FeatureCollection(months.map(per_month))


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    import datetime as dt

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get("EE_PROJECT_ID", "YOUR_GEE_PROJECT_ID"),
                    help="Google Cloud / Earth Engine project id "
                         "(or set EE_PROJECT_ID env var)")
    ap.add_argument("--start", default="2021-01-01", help="series start date (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.project == "YOUR_GEE_PROJECT_ID":
        log.error("No project id. Pass --project <ID> or set EE_PROJECT_ID. "
                  "Find it at https://console.cloud.google.com (project selector).")
        sys.exit(1)

    import pandas as pd
    ee = init_ee(args.project)

    with open(GEOJSON) as f:
        fc = json.load(f)

    # months from start to now
    start = dt.date.fromisoformat(args.start)
    today = dt.date.today()
    n_months = (today.year - start.year) * 12 + (today.month - start.month) + 1
    log.info(f"Series: {args.start} -> {today} ({n_months} months)")

    rows = []
    cat_by_lake = {}
    for feat in fc["features"]:
        name = feat["properties"]["name"]
        cat = feat["properties"].get("category", "unknown")
        cat_by_lake[name] = cat
        geom = ee.Geometry(feat["geometry"])
        log.info(f"[{name}] ({cat}) querying Sentinel-2 ...")
        monthly = build_monthly_fc(ee, geom, name, args.start, n_months)
        try:
            data = monthly.getInfo()
        except Exception as e:
            log.error(f"  GEE query failed for {name}: {e}")
            continue
        got = 0
        for ft in data["features"]:
            p = ft["properties"]
            rows.append({
                "lake": p["lake"],
                "category": cat,
                "date": p["date"],
                "ndci_mean": p.get("ndci_mean"),
                "water_px": p.get("water_px", 0),
                "n_scenes": p.get("n_scenes", 0),
            })
            if p.get("ndci_mean") is not None:
                got += 1
        log.info(f"  {got}/{n_months} months with valid NDCI")

    if not rows:
        log.error("No data returned. Check project id, auth, and polygons.")
        sys.exit(1)

    df = pd.DataFrame(rows).sort_values(["lake", "date"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(OUT_MONTHLY), exist_ok=True)
    df.to_csv(OUT_MONTHLY, index=False)
    log.info(f"Saved monthly series -> {OUT_MONTHLY}  ({len(df)} rows)")

    # ── Per-lake summary ──
    valid = df.dropna(subset=["ndci_mean"])
    summary = []
    for lake, g in valid.groupby("lake"):
        g = g.sort_values("date")
        summary.append({
            "lake": lake,
            "category": cat_by_lake.get(lake, "unknown"),
            "n_months": int(len(g)),
            "ndci_mean": round(float(g["ndci_mean"].mean()), 4),
            "ndci_median": round(float(g["ndci_mean"].median()), 4),
            "ndci_p75": round(float(g["ndci_mean"].quantile(0.75)), 4),
            "ndci_latest": round(float(g["ndci_mean"].iloc[-1]), 4),
            "latest_date": g["date"].iloc[-1],
        })
    sdf = pd.DataFrame(summary).sort_values(["category", "lake"])
    sdf.to_csv(OUT_SUMMARY, index=False)
    log.info(f"Saved summary -> {OUT_SUMMARY}")
    print("\n" + sdf.to_string(index=False))

    # ── Plot: polluted vs clean-reference ──
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(OUT_PLOT), exist_ok=True)
        fig, ax = plt.subplots(figsize=(13, 6))
        colors = {"polluted": "#b22222", "moderate": "#daa520",
                  "clean_reference": "#2e8b57", "unknown": "#888888"}
        styles = {"polluted": "-", "moderate": "--", "clean_reference": ":"}
        for lake, g in valid.groupby("lake"):
            g = g.sort_values("date")
            cat = cat_by_lake.get(lake, "unknown")
            ax.plot(g["date"], g["ndci_mean"], styles.get(cat, "-"),
                    color=colors.get(cat, "#888"), marker="o", ms=3, lw=1.6,
                    label=f"{lake} ({cat})")
        ax.set_title("Sentinel-2 NDCI (chlorophyll proxy) — monthly mean over water pixels")
        ax.set_ylabel("NDCI  (higher = more chlorophyll / eutrophication)")
        ax.set_xlabel("Month")
        ax.axhline(0, color="k", lw=0.5, alpha=0.4)
        step = max(1, len(valid["date"].unique()) // 20)
        xt = sorted(valid["date"].unique())[::step]
        ax.set_xticks(xt)
        ax.tick_params(axis="x", rotation=90, labelsize=7)
        ax.legend(fontsize=8, ncol=2)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT_PLOT, dpi=140)
        log.info(f"Saved plot -> {OUT_PLOT}")
    except Exception as e:
        log.warning(f"Plot generation skipped: {e}")

    print(f"\nDone. Monthly: {OUT_MONTHLY}\nSummary: {OUT_SUMMARY}\nPlot: {OUT_PLOT}")


if __name__ == "__main__":
    main()
