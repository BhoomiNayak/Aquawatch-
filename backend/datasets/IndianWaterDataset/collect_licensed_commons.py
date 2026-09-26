"""
License-aware image collector for the AquaWatch Indian water benchmark.

Why this exists
---------------
The original `scrape_indian_water.py` uses Google Image crawling, which captures
NO license or attribution data. Those images have unknown, presumptively
copyrighted provenance and cannot be redistributed in a published benchmark.

This script pulls from Wikimedia Commons instead. The Commons API returns the
license short-name, the author, and the source URL for every file, so each
downloaded image ships with the attribution a reviewer (or a journal) will ask
for. Only files under a free license (CC0 / public-domain / CC-BY / CC-BY-SA)
are kept.

Output
------
    commons_licensed/<source_category>/<filename>      downloaded images
    commons_metadata.csv                               provenance + attribution

The metadata CSV is annotation-compatible: it carries the same
`annotator_1/2/3` and `annotation_low_moderate_high` columns as
`image_metadata.csv`, so the existing labeling + fleiss_kappa workflow works
unchanged.

Usage
-----
    pip install requests
    python collect_licensed_commons.py
    python collect_licensed_commons.py --per-query 40 --out commons_licensed

Notes
-----
- Commons results change over time. The metadata CSV records the collection
  date and the exact source page URL for reproducibility.
- Human curation is still required: not every returned image is genuinely a
  polluted Indian water body. Review before labeling.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("This script needs `requests`. Install with:  pip install requests")

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "AquaWatch-benchmark-collector/1.0 "
    "(citizen-science water quality research; contact: project maintainer)"
)

# Search terms grouped by the source_category recorded in metadata.
# Kept aligned with the Google scraper's intent (polluted Indian water bodies)
# but phrased for Commons' text index.
SEARCH_QUERIES = {
    "Bellandur_Lake_Bangalore": "Bellandur lake Bangalore",
    "Yamuna_River_Delhi": "Yamuna river Delhi pollution",
    "Hussain_Sagar_Hyderabad": "Hussain Sagar Hyderabad lake",
    "Polluted_Lakes_India": "polluted lake India",
    "Dirty_Rivers_India": "polluted river India",
    "Urban_Drains_India": "sewage drain India water",
}

# Machine-readable license codes (from extmetadata "License") that are safe to
# redistribute. Matched case-insensitively as a prefix/exact.
FREE_LICENSE_PREFIXES = (
    "cc0",
    "cc-by",        # covers cc-by-2.0, cc-by-3.0, cc-by-4.0
    "cc-by-sa",     # covers all cc-by-sa-*
    "pd",           # public domain markers (pd, pd-self, pd-us, ...)
    "public domain",
)

# File types we accept (skip svg/pdf/gif etc.)
ALLOWED_EXT = {".jpg", ".jpeg", ".png"}


def _get(params: dict) -> dict:
    """Single Commons API GET with basic retry."""
    params = {**params, "format": "json", "formatversion": "2"}
    for attempt in range(4):
        try:
            r = requests.get(
                API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network hiccup -> back off
            wait = 2 ** attempt
            print(f"  API error ({exc}); retry in {wait}s")
            time.sleep(wait)
    return {}


def search_files(query: str, limit: int) -> list[str]:
    """Return File: titles matching a query in the File namespace (ns 6)."""
    data = _get(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": 6,
            "srlimit": limit,
        }
    )
    hits = data.get("query", {}).get("search", [])
    return [h["title"] for h in hits]


def file_info(titles: list[str], thumb_width: int) -> list[dict]:
    """Fetch imageinfo (url + thumbnail url + extmetadata) for File: titles.

    We request a bounded-width thumbnail (``iiurlwidth``) because Wikimedia
    explicitly asks clients to pull thumbnails rather than hammering the
    original full-resolution files on upload.wikimedia.org.
    """
    if not titles:
        return []
    data = _get(
        {
            "action": "query",
            "titles": "|".join(titles),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": thumb_width,
        }
    )
    return data.get("query", {}).get("pages", [])


def _meta(extmeta: dict, key: str) -> str:
    v = extmeta.get(key, {})
    val = v.get("value", "") if isinstance(v, dict) else ""
    # extmetadata values often contain HTML; strip tags for a clean CSV.
    return re.sub(r"<[^>]+>", "", str(val)).strip()


def is_free(license_code: str) -> bool:
    lc = license_code.lower().strip()
    return any(lc.startswith(p) for p in FREE_LICENSE_PREFIXES)


def safe_name(title: str, url: str) -> str:
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext not in ALLOWED_EXT:
        return ""
    stem = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
    return f"{stem}{ext}"


def download(url: str, dest: Path) -> bool:
    """Download with backoff. Honors HTTP 429 (Wikimedia rate limiting)."""
    for attempt in range(5):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"    rate limited (429); waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            dest.write_bytes(r.content)
            return True
        except Exception as exc:
            wait = 2 ** attempt
            print(f"    download error ({exc}); retry in {wait}s")
            time.sleep(wait)
    print("    download failed after retries")
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-query", type=int, default=40,
                    help="max candidate files to inspect per query (default 40)")
    ap.add_argument("--out", default="commons_licensed",
                    help="output image directory (default commons_licensed)")
    ap.add_argument("--csv", default="commons_metadata.csv",
                    help="output metadata CSV (default commons_metadata.csv)")
    ap.add_argument("--thumb-width", type=int, default=1024,
                    help="download bounded-width thumbnails (default 1024px)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    today = _dt.date.today().isoformat()

    rows: list[dict] = []
    kept = 0
    skipped_license = 0
    seq = 0

    for category, query in SEARCH_QUERIES.items():
        print(f"\n[{category}] searching Commons for: {query!r}")
        titles = search_files(query, args.per_query)
        print(f"  {len(titles)} candidate files")
        cat_dir = out_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        # imageinfo supports batches; 20 titles per request is polite.
        for i in range(0, len(titles), 20):
            for page in file_info(titles[i:i + 20], args.thumb_width):
                info = (page.get("imageinfo") or [{}])[0]
                url = info.get("url", "")
                # Prefer the bounded-width thumbnail (Wikimedia's recommended
                # path); fall back to the original only if no thumb was made.
                dl_url = info.get("thumburl") or url
                extmeta = info.get("extmetadata", {}) or {}
                lic_code = _meta(extmeta, "License")
                lic_name = _meta(extmeta, "LicenseShortName")

                if not url or not is_free(lic_code):
                    skipped_license += 1
                    continue

                fname = safe_name(page.get("title", ""), url)
                if not fname:
                    continue

                dest = cat_dir / fname
                if not dest.exists() and not download(dl_url, dest):
                    continue

                seq += 1
                kept += 1
                rows.append(
                    {
                        "image_id": f"commons_{seq:04d}",
                        "filename": f"{category}/{fname}",
                        "source_category": category,
                        "source_page": page.get("title", ""),
                        "source_url": info.get("descriptionurl", url),
                        "license": lic_name or lic_code,
                        "license_code": lic_code,
                        "author": _meta(extmeta, "Artist"),
                        "attribution": _meta(extmeta, "Credit"),
                        "collected_on": today,
                        "annotation_low_moderate_high": "",
                        "annotator_1": "",
                        "annotator_2": "",
                        "annotator_3": "",
                        "notes": "",
                    }
                )
                time.sleep(1.0)  # be polite to Commons / avoid 429

    if not rows:
        print("\nNo free-licensed images were collected. Try widening the queries "
              "or increasing --per-query.")
        return

    fieldnames = list(rows[0].keys())
    with open(args.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\nDone.")
    print(f"  kept (free license):   {kept}")
    print(f"  skipped (non-free/no license): {skipped_license}")
    print(f"  images -> {out_dir.resolve()}")
    print(f"  metadata -> {Path(args.csv).resolve()}")
    print("\nNext: human-curate (remove non-water / non-India / duplicates), "
          "then label annotator_1/2/3 per LABELING_GUIDE.md.")


if __name__ == "__main__":
    main()
