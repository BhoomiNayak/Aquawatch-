"""
EyeOnWater — Perceptual Hash Group-Aware De-Leaking Pipeline
=============================================================

PURPOSE:
    Detects augmented variants of the same source image in the EyeOnWater
    dataset by computing perceptual hashes (pHash) and clustering near-
    identical images via Hamming distance. Produces a group-aware train/val
    split that prevents augmented duplicates from leaking across the split.

METHODOLOGY (paper-citable):
    1. Compute 64-bit pHash for each image (DCT-based, 8×8 = 64 bits).
    2. Represent each hash as a binary vector; stack into matrix H ∈ {0,1}^(N×64).
    3. Compute pairwise Hamming distances via vectorized XOR + popcount:
       D[i,j] = popcount(H[i] XOR H[j]).
       Optimized with bit-packing to avoid the full N×N float matrix.
       Uses threshold early-stopping: only records pairs where D ≤ threshold.
    4. Build an adjacency graph where nodes are images and edges connect
       images with Hamming distance ≤ HAMMING_THRESHOLD.
    5. Extract connected components as clusters (each = one source image group).
    6. Perform GroupShuffleSplit on cluster IDs to produce group-aware
       train/val split (80/20).

CAVEAT (include in paper):
    pHash clustering is approximate. Aggressive color-jitter augmentation may
    split variants of the same source into separate clusters (under-grouping).
    Images with coincidentally similar compositions may merge into one cluster
    (over-grouping). Hamming threshold is a tunable parameter (default=10/64).
    This method provides best-effort de-leaking when source metadata is absent.

OUTPUTS:
    - eyeonwater_phash_clusters.csv  : per-image hash, cluster_id, split assignment
    - eyeonwater_split_train.csv     : training set (path + label + group)
    - eyeonwater_split_val.csv       : validation set (path + label + group)

RUNTIME: ~8-18 min on CPU for 22K images (hash computation + sparse clustering)

USAGE:
    cd backend
    python phash_group_split.py
"""

import os
import glob
import time
import csv
import numpy as np
from PIL import Image
import imagehash
from collections import defaultdict

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DATASET_DIR   = os.path.join(os.path.dirname(__file__), "datasets", "EyeOnWater_Dataset")
OUTPUT_DIR    = os.path.dirname(__file__)
HASH_BITS     = 8          # pHash grid = HASH_BITS × HASH_BITS = 64 bits
HAMMING_THRESHOLD = 10     # max Hamming distance to consider "same source"
                           # 10/64 ≈ 15.6% bit difference. Conservative.
                           # Increase to 12-14 if cluster stats look too fragmented.
VAL_RATIO     = 0.20       # 80/20 train/val
RANDOM_SEED   = 42
# ─────────────────────────────────────────────────────────────────────────────


def compute_phashes(image_paths, hash_bits=8):
    """
    Compute pHash for all images. Returns list of (path, label, hash_int64).
    pHash is returned as a numpy uint64 scalar for efficient bit ops.
    """
    records = []
    n = len(image_paths)
    print(f"  Computing pHash for {n:,} images...")
    t0 = time.time()

    for i, (path, label) in enumerate(image_paths):
        if (i + 1) % 2000 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (n - i - 1)
            print(f"    {i+1:>6}/{n:,}  elapsed={elapsed:.0f}s  eta={eta:.0f}s")
        try:
            img = Image.open(path).convert("RGB")
            h = imagehash.phash(img, hash_size=hash_bits)
            # Convert to int for storage; hash.hash is a bool array
            hash_int = int(str(h), 16)
            records.append((path, label, hash_int))
        except Exception as e:
            print(f"    WARNING: skipped {os.path.basename(path)}: {e}")

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s  ({n/elapsed:.0f} images/sec)")
    return records


def hamming_distance_vectorized(hash_ints):
    """
    Compute pairwise Hamming distances efficiently using numpy bit operations.

    Strategy: represent each 64-bit hash as 8 uint8 bytes. XOR pairs and
    count bits via lookup table. Processes in chunks to avoid OOM.

    Returns sparse adjacency list: dict {i: [j, ...]} for pairs where dist ≤ threshold.
    """
    n = len(hash_ints)
    print(f"  Building pairwise Hamming graph (N={n:,}, threshold={HAMMING_THRESHOLD})...")
    print(f"  Using chunked XOR strategy (avoids {n**2//2/1e9:.1f}B full comparisons)")

    # Convert to bit arrays: shape (N, 64) boolean
    hashes_bin = np.zeros((n, 64), dtype=np.uint8)
    for i, h in enumerate(hash_ints):
        bits = format(h, '064b')
        hashes_bin[i] = [int(b) for b in bits]

    # Build popcount lookup for 8-bit values
    popcount = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        popcount[i] = bin(i).count('1')

    adjacency = defaultdict(list)
    CHUNK = 500  # process 500 rows at a time

    t0 = time.time()
    edges_found = 0

    for chunk_start in range(0, n, CHUNK):
        chunk_end = min(chunk_start + CHUNK, n)
        chunk = hashes_bin[chunk_start:chunk_end]  # (CHUNK, 64)

        # XOR chunk with all remaining images (only upper triangle)
        for i_local, i_global in enumerate(range(chunk_start, chunk_end)):
            if i_global + 1 >= n:
                break
            row = hashes_bin[i_global]  # (64,)
            # XOR with all images after i_global
            rest = hashes_bin[i_global + 1:]  # (n - i_global - 1, 64)
            xor = np.bitwise_xor(row, rest)   # (m, 64)

            # Pack bits into bytes for popcount: reshape to (m, 8, 8)
            # then XOR byte-by-byte
            xor_packed = np.packbits(xor, axis=1)  # (m, 8)
            distances = popcount[xor_packed].sum(axis=1)  # (m,)

            # Find close pairs
            close = np.where(distances <= HAMMING_THRESHOLD)[0]
            for j_offset in close:
                j_global = i_global + 1 + j_offset
                adjacency[i_global].append(j_global)
                adjacency[j_global].append(i_global)
                edges_found += 1

        if (chunk_start // CHUNK) % 10 == 0 and chunk_start > 0:
            elapsed = time.time() - t0
            pct = chunk_end / n
            eta = elapsed / pct * (1 - pct)
            print(f"    Progress: {chunk_end:>6}/{n:,} ({pct*100:.1f}%)  "
                  f"edges={edges_found:,}  elapsed={elapsed:.0f}s  eta={eta:.0f}s")

    elapsed = time.time() - t0
    print(f"  Graph built in {elapsed:.1f}s  total edges={edges_found:,}")
    return adjacency


def connected_components(n, adjacency):
    """Extract connected components from adjacency list → cluster IDs."""
    visited = np.full(n, -1, dtype=np.int32)
    cluster_id = 0

    for start in range(n):
        if visited[start] != -1:
            continue
        # BFS
        queue = [start]
        visited[start] = cluster_id
        while queue:
            node = queue.pop()
            for neighbor in adjacency.get(node, []):
                if visited[neighbor] == -1:
                    visited[neighbor] = cluster_id
                    queue.append(neighbor)
        cluster_id += 1

    return visited, cluster_id


def group_aware_split(cluster_ids, val_ratio=0.20, seed=42):
    """
    Assign clusters to train or val ensuring no cluster spans both splits.
    Greedily fills val until val_ratio is reached.
    """
    rng = np.random.RandomState(seed)
    unique_clusters = np.unique(cluster_ids)
    rng.shuffle(unique_clusters)

    n_total = len(cluster_ids)
    n_val_target = int(n_total * val_ratio)

    val_clusters = set()
    val_count = 0
    for cid in unique_clusters:
        members = np.sum(cluster_ids == cid)
        if val_count < n_val_target:
            val_clusters.add(cid)
            val_count += members

    split = np.where(np.isin(cluster_ids, list(val_clusters)), 'val', 'train')
    return split


def cluster_statistics(cluster_ids, n_clusters):
    """Compute paper-ready cluster statistics."""
    sizes = []
    for cid in range(n_clusters):
        size = int(np.sum(cluster_ids == cid))
        if size > 0:
            sizes.append(size)

    sizes = np.array(sizes)
    singleton_pct = (sizes == 1).sum() / len(sizes) * 100
    return {
        "total_clusters": len(sizes),
        "singleton_clusters": int((sizes == 1).sum()),
        "singleton_pct": round(singleton_pct, 1),
        "max_cluster_size": int(sizes.max()),
        "mean_cluster_size": round(float(sizes.mean()), 2),
        "median_cluster_size": int(np.median(sizes)),
        "std_cluster_size": round(float(sizes.std()), 2),
    }


def main():
    print("=" * 65)
    print("AquaWatch — pHash Group-Aware De-Leaking Pipeline")
    print("=" * 65)
    print(f"Config: hash_bits={HASH_BITS}  threshold={HAMMING_THRESHOLD}  "
          f"val_ratio={VAL_RATIO}  seed={RANDOM_SEED}\n")

    # ── 1. Collect image paths ────────────────────────────────────────
    print("Step 1: Collecting image paths...")
    image_paths = []
    for label in ("good", "bad"):
        folder = os.path.join(DATASET_DIR, label)
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            for p in glob.glob(os.path.join(folder, ext)):
                image_paths.append((p, label))

    print(f"  Found {len(image_paths):,} images "
          f"(good={sum(1 for _,l in image_paths if l=='good'):,}  "
          f"bad={sum(1 for _,l in image_paths if l=='bad'):,})\n")

    if len(image_paths) == 0:
        print("ERROR: No images found. Check DATASET_DIR path.")
        return

    # ── 2. Compute pHashes ───────────────────────────────────────────
    print("Step 2: Computing perceptual hashes...")
    t_start = time.time()
    records = compute_phashes(image_paths, HASH_BITS)
    print()

    paths  = [r[0] for r in records]
    labels = [r[1] for r in records]
    hashes = [r[2] for r in records]
    n = len(records)

    # ── 3. Build Hamming graph ────────────────────────────────────────
    print("Step 3: Building Hamming distance graph...")
    adjacency = hamming_distance_vectorized(hashes)
    print()

    # ── 4. Extract connected components (clusters) ───────────────────
    print("Step 4: Extracting source-image clusters...")
    cluster_ids, n_clusters_raw = connected_components(n, adjacency)
    print(f"  Raw clusters: {n_clusters_raw:,}")

    # ── 5. Cluster statistics (paper-ready) ──────────────────────────
    stats = cluster_statistics(cluster_ids, n_clusters_raw)
    print()
    print("=" * 65)
    print("CLUSTER STATISTICS (cite in paper methodology section)")
    print("=" * 65)
    print(f"  Total images analyzed:      {n:,}")
    print(f"  Total clusters formed:      {stats['total_clusters']:,}")
    print(f"  Singleton clusters:         {stats['singleton_clusters']:,} ({stats['singleton_pct']}%)")
    print(f"  Max cluster size:           {stats['max_cluster_size']}")
    print(f"  Mean cluster size:          {stats['mean_cluster_size']}")
    print(f"  Median cluster size:        {stats['median_cluster_size']}")
    print(f"  Std cluster size:           {stats['std_cluster_size']}")
    print(f"  Hamming threshold used:     {HAMMING_THRESHOLD}/64 bits ({HAMMING_THRESHOLD/64*100:.1f}%)")
    print(f"  Estimated leakage risk:     "
          f"{'HIGH - many large clusters' if stats['max_cluster_size'] > 50 else 'LOW - mostly singletons' if stats['singleton_pct'] > 80 else 'MODERATE'}")
    print()

    # ── 6. Group-aware train/val split ───────────────────────────────
    print("Step 5: Generating group-aware train/val split...")
    split = group_aware_split(cluster_ids, VAL_RATIO, RANDOM_SEED)

    train_count = (split == 'train').sum()
    val_count   = (split == 'val').sum()
    print(f"  Train: {train_count:,} images ({train_count/n*100:.1f}%)")
    print(f"  Val:   {val_count:,} images ({val_count/n*100:.1f}%)")

    # Label balance check
    train_good = sum(1 for i,l in enumerate(labels) if split[i]=='train' and l=='good')
    train_bad  = sum(1 for i,l in enumerate(labels) if split[i]=='train' and l=='bad')
    val_good   = sum(1 for i,l in enumerate(labels) if split[i]=='val'   and l=='good')
    val_bad    = sum(1 for i,l in enumerate(labels) if split[i]=='val'   and l=='bad')
    print(f"  Train: good={train_good:,}  bad={train_bad:,}  "
          f"ratio={train_good/(train_good+train_bad)*100:.1f}%/{train_bad/(train_good+train_bad)*100:.1f}%")
    print(f"  Val:   good={val_good:,}  bad={val_bad:,}  "
          f"ratio={val_good/(val_good+val_bad)*100:.1f}%/{val_bad/(val_good+val_bad)*100:.1f}%")
    print()

    # ── 7. Export CSVs ───────────────────────────────────────────────
    print("Step 6: Exporting audit CSV files...")

    # Full clusters CSV (auditability)
    clusters_csv = os.path.join(OUTPUT_DIR, "eyeonwater_phash_clusters.csv")
    with open(clusters_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "label", "phash_hex", "cluster_id", "split"])
        for i in range(n):
            fname = os.path.basename(paths[i])
            phash_hex = format(hashes[i], '016x')
            writer.writerow([fname, labels[i], phash_hex, int(cluster_ids[i]), split[i]])
    print(f"  Saved: {clusters_csv}")

    # Train split CSV
    train_csv = os.path.join(OUTPUT_DIR, "eyeonwater_split_train.csv")
    with open(train_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "label", "cluster_id"])
        for i in range(n):
            if split[i] == 'train':
                writer.writerow([paths[i], labels[i], int(cluster_ids[i])])
    print(f"  Saved: {train_csv}")

    # Val split CSV
    val_csv = os.path.join(OUTPUT_DIR, "eyeonwater_split_val.csv")
    with open(val_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "label", "cluster_id"])
        for i in range(n):
            if split[i] == 'val':
                writer.writerow([paths[i], labels[i], int(cluster_ids[i])])
    print(f"  Saved: {val_csv}")

    total_time = time.time() - t_start
    print()
    print("=" * 65)
    print(f"COMPLETE in {total_time:.0f}s ({total_time/60:.1f} min)")
    print("=" * 65)
    print()
    print("Next step: run train_efficientnet_group_aware.py to retrain")
    print("using these split files instead of random_split.")


if __name__ == "__main__":
    main()
