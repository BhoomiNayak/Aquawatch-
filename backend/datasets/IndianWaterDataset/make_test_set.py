import csv
import shutil
from pathlib import Path
from PIL import Image

RAW = Path("dataset_indian_raw")
OUT = Path("indian_test_set_200")
CSV = Path("image_metadata.csv")
TARGET = 200

def main():
    if not RAW.exists():
        print("Run the scraper and cleaner first.")
        return

    candidates = []
    for category_dir in sorted(RAW.iterdir()):
        if not category_dir.is_dir():
            continue
        for p in sorted(category_dir.iterdir()):
            if p.is_file():
                try:
                    with Image.open(p) as im:
                        im.verify()
                    candidates.append((category_dir.name, p))
                except Exception:
                    pass

    print(f"Valid image candidates found: {len(candidates)}")
    if len(candidates) < TARGET:
        print(f"WARNING: fewer than {TARGET} valid images were found.")
        print("Run the scraper again with different queries or increase IMAGES_PER_QUERY.")
        return

    OUT.mkdir(exist_ok=True)

    # Select up to a balanced number from each category, then fill remaining slots.
    groups = {}
    for category, path in candidates:
        groups.setdefault(category, []).append(path)

    selected = []
    categories = sorted(groups)
    per_category = TARGET // len(categories)
    for category in categories:
        selected.extend((category, p) for p in groups[category][:per_category])

    selected_paths = {p for _, p in selected}
    for category, p in candidates:
        if len(selected) >= TARGET:
            break
        if p not in selected_paths:
            selected.append((category, p))
            selected_paths.add(p)

    rows = []
    for i, (category, src) in enumerate(selected[:TARGET], 1):
        dest = OUT / f"image_{i:03d}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        rows.append({
            "image_id": f"image_{i:03d}",
            "filename": dest.name,
            "source_category": category,
            "annotation_low_moderate_high": "",
            "annotator_1": "",
            "annotator_2": "",
            "annotator_3": "",
            "notes": ""
        })

    with CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCreated {len(rows)} images in: {OUT.resolve()}")
    print(f"Created metadata template: {CSV.resolve()}")
    print("IMPORTANT: manually review these images and replace/remove irrelevant images before final submission.")

if __name__ == "__main__":
    main()
