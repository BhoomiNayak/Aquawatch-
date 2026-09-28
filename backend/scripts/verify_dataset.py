#!/usr/bin/env python3
"""
Image License Verification Script
Helps identify images that need license verification before publication.
"""

import os
import csv
from PIL import Image
from collections import Counter

def verify_dataset(base_dir='backend/data/local_benchmark'):
    """Verify dataset integrity and flag licensing concerns."""

    images_dir = os.path.join(base_dir, 'images')
    csv_path = os.path.join(base_dir, 'indian_validation_set.csv')

    print("=" * 60)
    print("DATASET VERIFICATION REPORT")
    print("=" * 60)

    # Check 1: Image count
    images = sorted([f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.png'))])
    print(f"\n[1] Image Count: {len(images)} files")
    print(f"    Status: {'PASS' if 200 <= len(images) <= 300 else 'FAIL'} (required: 200-300)")

    # Check 2: CSV integrity
    print(f"\n[2] CSV Metadata:")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"    Rows: {len(rows)}")
        print(f"    Columns: {reader.fieldnames}")

        # Check for NaN
        nan_count = sum(1 for row in rows for v in row.values() if v is None or v.strip() == '')
        print(f"    Empty values: {nan_count}")
        print(f"    Status: {'PASS' if nan_count == 0 else 'FAIL'}")

        # Check consensus
        consensus_ok = 0
        for row in rows:
            votes = [int(row['annotator_1']), int(row['annotator_2']), int(row['annotator_3'])]
            mode = Counter(votes).most_common(1)[0][0]
            if mode == int(row['consensus_label']):
                consensus_ok += 1
        print(f"    Consensus matches mode: {consensus_ok}/{len(rows)}")
        print(f"    Status: {'PASS' if consensus_ok == len(rows) else 'FAIL'}")

    # Check 3: Image dimensions
    print(f"\n[3] Image Quality Check:")
    small_images = []
    for img_name in images:
        img_path = os.path.join(images_dir, img_name)
        with Image.open(img_path) as img:
            w, h = img.size
            if w < 500 or h < 500:
                small_images.append((img_name, w, h))
    print(f"    Images <500px: {len(small_images)}")
    print(f"    Status: {'PASS' if len(small_images) == 0 else 'WARNING'}")

    # Check 4: File naming
    print(f"\n[4] File Naming:")
    naming_ok = all(img.startswith('IND_') and img.endswith('.jpg') for img in images)
    print(f"    Format IND_XXX.jpg: {'PASS' if naming_ok else 'FAIL'}")

    # Check 5: Licensing warning
    print(f"\n[5] LICENSING WARNING:")
    print(f"    This dataset contains web-scraped images")
    print(f"    VERIFY all image licenses before publication")
    print(f"    See LICENSES.md for details")
    print(f"    Replace commercial/stock photos with open-license images")

    print(f"\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)

    return {
        'image_count': len(images),
        'csv_rows': len(rows),
        'consensus_ok': consensus_ok == len(rows),
        'small_images': len(small_images),
        'naming_ok': naming_ok
    }

if __name__ == '__main__':
    import sys
    verify_dataset(sys.argv[1] if len(sys.argv) > 1 else 'backend/data/local_benchmark')
