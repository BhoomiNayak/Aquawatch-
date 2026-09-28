"""
extract_image_provenance.py
===========================
Recover *verifiable* provenance/license evidence embedded in the benchmark
image files and record it. This does NOT invent licenses: fields with no
embedded evidence are left UNKNOWN / UNRESOLVED.

For each image in datasets/local_benchmark/images/ it extracts:
  - EXIF Artist (0x013B), Copyright (0x8298), ImageDescription (0x010E),
    XPAuthor (0x9C9D)
  - XMP rights / usage-terms if present in the file
  - sha256 (exact-duplicate / integrity key) and pHash (source-matching key)

Output: rewrites docs/benchmark_provenance.csv with columns
  image_id, water_body_name, location_city, exif_artist, exif_copyright,
  exif_description, xmp_rights, sha256, phash, source_url, license,
  collection_date, evidence_status

evidence_status:
  EXIF_RIGHTS_FOUND  — an author/copyright/rights field was present in the file
  NO_EMBEDDED_EVIDENCE — file carries no rights metadata (still UNRESOLVED)

Usage:
  cd backend
  python scripts/extract_image_provenance.py
"""
from __future__ import annotations
import csv, hashlib, os
from PIL import Image, ExifTags

BASE = os.path.dirname(os.path.dirname(__file__))
IMG_DIR = os.path.join(BASE, "datasets", "local_benchmark", "images")
BENCH = os.path.join(BASE, "datasets", "local_benchmark", "indian_validation_set.csv")
OUT = os.path.join(BASE, "..", "docs", "benchmark_provenance.csv")

TAG = {v: k for k, v in ExifTags.TAGS.items()}  # name -> id


def _clean(v):
    if v is None:
        return ""
    if isinstance(v, bytes):
        # XPAuthor is UTF-16LE; others may be latin-1
        for enc in ("utf-16-le", "utf-8", "latin-1"):
            try:
                return v.decode(enc).strip("\x00").strip()
            except Exception:
                continue
        return ""
    return str(v).strip()


def extract(path: str) -> dict:
    out = {"exif_artist": "", "exif_copyright": "", "exif_description": "",
           "xmp_rights": "", "phash": ""}
    try:
        im = Image.open(path)
        exif = im.getexif()
        if exif:
            out["exif_artist"] = _clean(exif.get(TAG.get("Artist")))
            out["exif_copyright"] = _clean(exif.get(TAG.get("Copyright")))
            out["exif_description"] = _clean(exif.get(TAG.get("ImageDescription")))
            xp = exif.get(TAG.get("XPAuthor"))
            if xp and not out["exif_artist"]:
                out["exif_artist"] = _clean(xp)
        # XMP (PNG/JPEG may embed it in info)
        xmp = im.info.get("xmp") or im.info.get("XML:com.adobe.xmp")
        if xmp:
            x = _clean(xmp)
            for tag in ("dc:rights", "xmpRights:UsageTerms", "cc:license",
                        "xmpRights:WebStatement"):
                if tag in x:
                    out["xmp_rights"] = "present (see file XMP)"
                    break
        # perceptual hash (median DCT-free avg hash fallback if imagehash absent)
        try:
            import imagehash
            out["phash"] = str(imagehash.phash(im))
        except Exception:
            out["phash"] = ""
    except Exception as e:
        out["exif_description"] = f"(read error: {e})"
    return out


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    meta = {r["image_id"]: r for r in csv.DictReader(open(BENCH))}
    rows = []
    n_rights = 0
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    for fn in files:
        path = os.path.join(IMG_DIR, fn)
        m = meta.get(fn, {})
        ev = extract(path)
        has_rights = bool(ev["exif_artist"] or ev["exif_copyright"] or ev["xmp_rights"])
        if has_rights:
            n_rights += 1
        rows.append({
            "image_id": fn,
            "water_body_name": m.get("water_body_name", ""),
            "location_city": m.get("location_city", ""),
            "exif_artist": ev["exif_artist"],
            "exif_copyright": ev["exif_copyright"],
            "exif_description": ev["exif_description"],
            "xmp_rights": ev["xmp_rights"],
            "sha256": sha256(path),
            "phash": ev["phash"],
            # honest defaults — NOT fabricated
            "source_url": "UNKNOWN",
            "license": ev["exif_copyright"] or ev["xmp_rights"] or "UNKNOWN",
            "collection_date": "UNKNOWN",
            "evidence_status": "EXIF_RIGHTS_FOUND" if has_rights else "NO_EMBEDDED_EVIDENCE",
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fields = ["image_id", "water_body_name", "location_city", "exif_artist",
              "exif_copyright", "exif_description", "xmp_rights", "sha256",
              "phash", "source_url", "license", "collection_date", "evidence_status"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Scanned {len(rows)} images")
    print(f"  with embedded rights metadata: {n_rights}")
    print(f"  no embedded evidence (UNRESOLVED): {len(rows) - n_rights}")
    print(f"  wrote {os.path.normpath(OUT)}")
    if n_rights == 0:
        print("\n  NOTE: no image carried author/copyright/rights metadata. Per-image")
        print("  licensing remains UNRESOLVED and must be established from source records.")


if __name__ == "__main__":
    main()
