import csv
import hashlib
import re
import shutil
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_DIR / "global_water_pollution"
OUTPUT_DIR = PROJECT_DIR / "clean_water_pollution_dataset"
METADATA_FILE = OUTPUT_DIR / "image_metadata.csv"
TARGET_PER_LABEL = 30

LABELS = {
    "Garbage_in_Water": "garbage",
    "Plastic_Pollution": "plastic",
    "Sewage_Wastewater": "sewage",
    "Polluted_Rivers": "polluted_rivers",
    "Polluted_Lakes": "polluted_lakes",
    "Foam_Algae_Pollution": "algal_foam",
    "Marine_Pollution": "marine",
    "Oil_Chemical_Pollution": "oily_chemical",
}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
EXCLUDE_TERMS = {
    "chart", "diagram", "graph", "map", "plan", "silhouette", "icon",
    "logo", "sign", "svg", "infographic", "awareness", "treatment_plant",
    "wastewater_plant", "garbage_can", "family", "ducks", "hatchery",
    "satellite", "aerial_view", "residential_area", "pipeline", "infrastructure",
    "sightseeing_boat", "diesel_powered", "boat_plies", "oil_cleanup",
    "cleaninig_oil", "boats_on_oil", "harbour", "log_boom", "motel",
    "sunset", "fisherman", "fishermen", "construction_site", "docks",
}


def normalize(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def image_content_hash(path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((64, 64))
        return hashlib.sha256(image.tobytes()).hexdigest()


def load_metadata():
    metadata_path = SOURCE_DIR / "image_metadata.csv"
    with metadata_path.open(newline="", encoding="utf-8") as file:
        return {row["filename"]: row for row in csv.DictReader(file)}


def is_relevant_photo(path, row):
    searchable = "_".join(
        normalize(row.get(field, ""))
        for field in ("filename", "search_query", "source_page")
    )
    return not any(term in searchable for term in EXCLUDE_TERMS)


def main():
    if not SOURCE_DIR.exists():
        raise SystemExit(f"Source folder not found: {SOURCE_DIR}")

    metadata = load_metadata()
    candidates = {label: [] for label in LABELS.values()}
    seen_hashes = set()
    skipped = {"unsupported": 0, "irrelevant": 0, "invalid": 0, "duplicate": 0}

    for source_category, label in LABELS.items():
        category_dir = SOURCE_DIR / source_category
        for source_path in sorted(category_dir.iterdir()):
            if not source_path.is_file() or source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped["unsupported"] += 1
                continue

            row = metadata.get(source_path.name, {})
            if not is_relevant_photo(source_path, row):
                skipped["irrelevant"] += 1
                continue

            try:
                with Image.open(source_path) as image:
                    image.verify()
                content_hash = image_content_hash(source_path)
            except Exception:
                skipped["invalid"] += 1
                continue

            if content_hash in seen_hashes:
                skipped["duplicate"] += 1
                continue

            seen_hashes.add(content_hash)
            candidates[label].append((source_path, row, content_hash))

    selected = []
    for label in sorted(candidates):
        selected.extend((label, item) for item in candidates[label][:TARGET_PER_LABEL])

    if len(selected) < 200:
        raise SystemExit(f"Only {len(selected)} suitable images found; need at least 200.")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    for label in sorted(candidates):
        (OUTPUT_DIR / label).mkdir(parents=True, exist_ok=True)

    rows = []
    for image_number, (label, (source_path, source_row, content_hash)) in enumerate(selected, 1):
        destination_name = f"{label}_{image_number:03d}{source_path.suffix.lower()}"
        destination = OUTPUT_DIR / label / destination_name
        shutil.copy2(source_path, destination)
        rows.append({
            "image_id": f"image_{image_number:03d}",
            "label": label,
            "filename": destination_name,
            "source_category": source_row.get("category", ""),
            "search_query": source_row.get("search_query", ""),
            "source_page": source_row.get("source_page", ""),
            "license": source_row.get("license", ""),
            "artist": source_row.get("artist", ""),
            "content_hash": content_hash,
        })

    with METADATA_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created {len(rows)} cleaned images in: {OUTPUT_DIR}")
    print(f"Metadata written to: {METADATA_FILE}")
    print("Images by label:")
    for label in sorted(candidates):
        print(f"  {label}: {min(len(candidates[label]), TARGET_PER_LABEL)}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()