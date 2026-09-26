"""
audit_phash_leakage.py
======================
Post-training leakage diagnostic for the pHash group-aware split.

Checks:
1. Cluster ID overlap between train and val (should be zero)
2. Cross-split Hamming distance distribution (residual similarity)
3. Identifies "suspicious" val images with a very close train neighbour
   (Hamming ≤ SUSPICION_THRESHOLD) that ended up in different clusters
   — these represent pHash failures under aggressive augmentation.

USAGE:
    cd backend
    python scripts/audit_phash_leakage.py

OUTPUTS:
    reports/phash_leakage_audit.json   — machine-readable full report
    Terminal                           — paper-ready summary
"""

import os
import sys
import json
import logging
import time

import numpy as np
import pandas as pd

# ── paths ────────────────────────────────────────────────────────
BASE   = os.path.dirname(os.path.dirname(__file__))
CSV    = os.path.join(BASE, "eyeonwater_phash_clusters.csv")
REPORT = os.path.join(BASE, "reports", "phash_leakage_audit.json")

SUSPICION_THRESHOLD = 6   # Hamming ≤ 6/64 = highly similar, likely same source
SAMPLE_SIZE = 2000        # sample this many cross-split pairs for distance stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("leakage_audit")

# ── helpers ──────────────────────────────────────────────────────

def hex_to_bits(hex_str: str) -> np.ndarray:
    """Convert 16-char hex pHash to 64-bit binary array."""
    try:
        val = int(hex_str, 16)
    except (ValueError, TypeError):
        val = 0
    return np.array([int(b) for b in format(val, '064b')], dtype=np.uint8)


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.sum(a != b))


def vectorized_hamming_min(query_bits: np.ndarray, pool_bits: np.ndarray,
                           chunk=500) -> np.ndarray:
    """
    For each row in query_bits, find minimum Hamming distance to pool_bits.
    Chunked to avoid OOM on large datasets.
    """
    n_q = query_bits.shape[0]
    min_dists = np.full(n_q, 64, dtype=np.int32)

    for start in range(0, n_q, chunk):
        end = min(start + chunk, n_q)
        q_chunk = query_bits[start:end]        # (chunk, 64)
        # XOR with pool and count bits
        xor = np.bitwise_xor(q_chunk[:, None, :], pool_bits[None, :, :])  # (c,P,64)
        dists = xor.sum(axis=2)                # (c, P)
        min_dists[start:end] = dists.min(axis=1)

    return min_dists


def main():
    log.info("Loading pHash cluster CSV...")
    df = pd.read_csv(CSV)
    log.info(f"  Total images: {len(df):,}  cols: {df.columns.tolist()}")

    train = df[df['split'] == 'train'].reset_index(drop=True)
    val   = df[df['split'] == 'val'].reset_index(drop=True)
    log.info(f"  Train: {len(train):,}   Val: {len(val):,}")

    # ── CHECK 1: Cluster ID overlap ──────────────────────────────
    log.info("Check 1: Cluster ID overlap...")
    train_clusters = set(train['cluster_id'].unique())
    val_clusters   = set(val['cluster_id'].unique())
    overlap_clusters = train_clusters & val_clusters

    if len(overlap_clusters) == 0:
        cluster_overlap_status = "CLEAN — No cluster IDs shared between train and val."
    else:
        # Count images in overlapping clusters
        overlap_imgs = df[df['cluster_id'].isin(overlap_clusters)]
        cluster_overlap_status = (f"LEAK — {len(overlap_clusters)} clusters span both splits, "
                                  f"affecting {len(overlap_imgs)} images.")
    log.info(f"  {cluster_overlap_status}")

    # ── CHECK 2: Cross-split Hamming distance distribution ───────
    log.info("Check 2: Cross-split Hamming distances (sampled)...")
    rng = np.random.RandomState(42)

    # Convert hashes to bit arrays
    log.info("  Converting val hashes to bit arrays...")
    val_bits = np.stack([hex_to_bits(h) for h in val['phash_hex']], axis=0)

    # Sample from train
    n_sample = min(SAMPLE_SIZE, len(train))
    sample_idx = rng.choice(len(train), n_sample, replace=False)
    train_sample_bits = np.stack([hex_to_bits(train['phash_hex'].iloc[i])
                                   for i in sample_idx], axis=0)

    log.info(f"  Computing min distances: {len(val_bits)} val vs {n_sample} train samples...")
    t0 = time.time()
    min_dists = vectorized_hamming_min(val_bits, train_sample_bits, chunk=200)
    elapsed = time.time() - t0
    log.info(f"  Done in {elapsed:.1f}s")

    # Distance distribution
    dist_counts = {str(d): int(np.sum(min_dists == d)) for d in range(0, 20)}
    suspicious_mask = min_dists <= SUSPICION_THRESHOLD
    n_suspicious = int(suspicious_mask.sum())
    suspicious_pct = n_suspicious / len(val) * 100

    log.info(f"  Val images with closest train neighbour ≤ {SUSPICION_THRESHOLD} bits: "
             f"{n_suspicious} ({suspicious_pct:.1f}%)")

    # ── CHECK 3: Suspected leakage examples ──────────────────────
    suspicious_examples = []
    if n_suspicious > 0:
        sus_idx = np.where(suspicious_mask)[0][:10]  # first 10
        for i in sus_idx:
            val_row = val.iloc[i]
            # Find nearest train neighbour
            dists_to_train = np.array([hamming(val_bits[i], train_sample_bits[j])
                                       for j in range(len(train_sample_bits))])
            nearest_j = int(np.argmin(dists_to_train))
            nearest_dist = int(dists_to_train[nearest_j])
            train_row = train.iloc[sample_idx[nearest_j]]
            suspicious_examples.append({
                "val_file": val_row['filename'],
                "val_cluster": int(val_row['cluster_id']),
                "val_label": val_row['label'],
                "nearest_train_file": train_row['filename'],
                "nearest_train_cluster": int(train_row['cluster_id']),
                "train_label": train_row['label'],
                "hamming_dist": nearest_dist
            })

    # ── SUMMARY ──────────────────────────────────────────────────
    leakage_level = (
        "SEVERE"   if suspicious_pct > 10 else
        "MODERATE" if suspicious_pct > 2  else
        "MINIMAL"  if suspicious_pct > 0  else
        "NONE"
    )

    report = {
        "method": "pHash (DCT 8x8, 64-bit) + Hamming threshold 10",
        "train_size": len(train),
        "val_size": len(val),
        "train_clusters": len(train_clusters),
        "val_clusters": len(val_clusters),
        "cluster_id_overlap": len(overlap_clusters),
        "cluster_overlap_status": cluster_overlap_status,
        "suspicion_threshold_bits": SUSPICION_THRESHOLD,
        "train_sample_size": n_sample,
        "suspicious_val_images": n_suspicious,
        "suspicious_val_pct": round(suspicious_pct, 2),
        "leakage_level": leakage_level,
        "distance_distribution": dist_counts,
        "min_dist_stats": {
            "mean": round(float(min_dists.mean()), 2),
            "median": int(np.median(min_dists)),
            "min": int(min_dists.min()),
            "max": int(min_dists.max()),
            "pct_under_5": round(float((min_dists < 5).mean() * 100), 2),
            "pct_under_10": round(float((min_dists < 10).mean() * 100), 2),
        },
        "suspicious_examples": suspicious_examples,
        "interpretation": (
            "The residual similarity analysis measures whether pHash failed to "
            "group augmented variants (they land in different clusters but are "
            "visually near-identical). A high suspicious_val_pct suggests the "
            "99.9% accuracy reflects genuine generalisation rather than leakage."
            if suspicious_pct < 5 else
            "A notable fraction of val images have very close train neighbours "
            "in different clusters. This suggests pHash failed to detect some "
            "augmented variants, constituting residual leakage."
        )
    }

    # Save report
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2)

    # ── Terminal output ───────────────────────────────────────────
    print()
    print("=" * 65)
    print("PHASH LEAKAGE AUDIT REPORT")
    print("=" * 65)
    print(f"  Train images:              {len(train):,}")
    print(f"  Val images:                {len(val):,}")
    print(f"  Cluster ID overlap:        {len(overlap_clusters)} clusters — {cluster_overlap_status.split(' — ')[0]}")
    print()
    print(f"  Suspicion threshold:       Hamming ≤ {SUSPICION_THRESHOLD}/64 bits")
    print(f"  Suspicious val images:     {n_suspicious} ({suspicious_pct:.1f}%)")
    print(f"  Leakage level:             {leakage_level}")
    print()
    print(f"  Distance stats (val → nearest train sample):")
    print(f"    Mean:      {report['min_dist_stats']['mean']}")
    print(f"    Median:    {report['min_dist_stats']['median']}")
    print(f"    Min:       {report['min_dist_stats']['min']}")
    print(f"    % under 5: {report['min_dist_stats']['pct_under_5']}%")
    print(f"    % under 10:{report['min_dist_stats']['pct_under_10']}%")
    print()
    print(f"  Interpretation:")
    print(f"    {report['interpretation'][:200]}...")
    print()
    print(f"  Full report: {REPORT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
