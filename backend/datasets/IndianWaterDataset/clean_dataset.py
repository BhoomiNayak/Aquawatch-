import os
import hashlib
from pathlib import Path
from PIL import Image

DATASET_FOLDER = Path("dataset_indian_raw")
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

def image_hash(path):
    with Image.open(path) as img:
        return hashlib.md5(img.convert("RGB").tobytes()).hexdigest()

def main():
    if not DATASET_FOLDER.exists():
        print(f"Folder not found: {DATASET_FOLDER}")
        print("Run scrape_indian_water.py first.")
        return

    seen = set()
    deleted_duplicates = 0
    deleted_bad = 0
    kept = 0

    for path in DATASET_FOLDER.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        try:
            h = image_hash(path)
            if h in seen:
                path.unlink()
                deleted_duplicates += 1
            else:
                seen.add(h)
                kept += 1
        except Exception as exc:
            print("Removing unreadable image:", path, "|", exc)
            try:
                path.unlink()
                deleted_bad += 1
            except OSError:
                pass

    print("\nCleaning completed.")
    print("Unique images kept:", kept)
    print("Duplicates removed:", deleted_duplicates)
    print("Unreadable files removed:", deleted_bad)

if __name__ == "__main__":
    main()
