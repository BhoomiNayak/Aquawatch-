"""
validation_audit_summary.py
============================
Combines leakage audit + benchmark results into a single
paper-ready JSON and terminal summary.

USAGE:
    cd backend
    python scripts/validation_audit_summary.py

OUTPUTS:
    reports/validation_audit_summary.json
"""

import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("audit_summary")

BASE         = os.path.dirname(os.path.dirname(__file__))
LEAKAGE_RPT  = os.path.join(BASE, "reports", "phash_leakage_audit.json")
BENCHMARK_RPT= os.path.join(BASE, "reports", "indian_benchmark_results.json")
SUMMARY_OUT  = os.path.join(BASE, "reports", "validation_audit_summary.json")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def main():
    print("=" * 65)
    print("AQUAWATCH — VALIDATION AUDIT SUMMARY")
    print("=" * 65)

    leakage  = load_json(LEAKAGE_RPT)
    benchmark= load_json(BENCHMARK_RPT)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "model": "EfficientNet-B0 (group-aware pHash split)",
        "dataset": "EyeOnWater (22,376 images, binary good/bad)",
        "split_method": "pHash clustering (DCT 8x8, Hamming threshold 10/64)",
    }

    # ── Leakage section ───────────────────────────────────────────
    if leakage:
        summary["leakage_audit"] = {
            "cluster_id_overlap":     leakage["cluster_id_overlap"],
            "cluster_overlap_status": leakage["cluster_overlap_status"],
            "suspicious_val_images":  leakage["suspicious_val_images"],
            "suspicious_val_pct":     leakage["suspicious_val_pct"],
            "leakage_level":          leakage["leakage_level"],
            "min_dist_mean":          leakage["min_dist_stats"]["mean"],
            "min_dist_median":        leakage["min_dist_stats"]["median"],
            "pct_under_5_bits":       leakage["min_dist_stats"]["pct_under_5"],
        }
        print(f"\n  LEAKAGE AUDIT")
        print(f"    Cluster ID overlap:     {leakage['cluster_id_overlap']}")
        print(f"    Suspicious val images:  {leakage['suspicious_val_images']} "
              f"({leakage['suspicious_val_pct']}%)")
        print(f"    Leakage level:          {leakage['leakage_level']}")
    else:
        summary["leakage_audit"] = "NOT RUN — run scripts/audit_phash_leakage.py first"
        print("\n  LEAKAGE AUDIT: Not run yet.")
        print("    Run: python scripts/audit_phash_leakage.py")

    # ── Accuracy comparison ───────────────────────────────────────
    internal_acc = None
    if benchmark and benchmark.get("internal_val_accuracy_phash"):
        internal_acc = benchmark["internal_val_accuracy_phash"]
    elif leakage:
        internal_acc = None  # not stored in leakage report

    original_random_acc = 0.998  # the original inflated number

    benchmark_acc = None
    if benchmark:
        benchmark_acc = benchmark["benchmark_metrics"]["accuracy"]

    summary["accuracy_comparison"] = {
        "original_random_split_acc": original_random_acc,
        "group_aware_phash_val_acc": internal_acc,
        "indian_benchmark_acc":      benchmark_acc,
        "random_vs_groupaware_delta": round(original_random_acc - internal_acc, 4)
                                       if internal_acc else None,
        "groupaware_vs_benchmark_delta": round(internal_acc - benchmark_acc, 4)
                                          if (internal_acc and benchmark_acc) else None,
    }

    print(f"\n  ACCURACY COMPARISON")
    print(f"    Original (random split):        {original_random_acc*100:.1f}%")
    if internal_acc:
        delta1 = (original_random_acc - internal_acc) * 100
        print(f"    Group-aware pHash val acc:      {internal_acc*100:.2f}%  "
              f"(Δ {delta1:+.1f}pp)")
    else:
        print(f"    Group-aware pHash val acc:      Training not complete yet")
    if benchmark_acc:
        print(f"    Indian benchmark (OOD) acc:     {benchmark_acc*100:.2f}%")
        if internal_acc:
            delta2 = (internal_acc - benchmark_acc) * 100
            print(f"    OOD generalisation gap:         {delta2:.1f}pp")
    else:
        print(f"    Indian benchmark (OOD) acc:     Not available yet")
        print(f"      → Add images to datasets/indian_validation_set/")
        print(f"      → Run: python scripts/evaluate_local_benchmark.py")

    # ── Benchmark section ─────────────────────────────────────────
    if benchmark:
        bm = benchmark["benchmark_metrics"]
        summary["benchmark_evaluation"] = {
            "total_images":   benchmark["total_images"],
            "class_dist":     benchmark["class_distribution"],
            "accuracy":       bm["accuracy"],
            "roc_auc":        bm["roc_auc"],
            "macro_f1":       bm["macro_f1"],
            "per_class":      bm["per_class"],
        }
        print(f"\n  BENCHMARK METRICS")
        print(f"    Images evaluated:  {benchmark['total_images']}")
        print(f"    ROC-AUC:           {bm['roc_auc']:.4f}")
        print(f"    Macro F1:          {bm['macro_f1']:.4f}")
        for cls, m in bm['per_class'].items():
            print(f"    {cls:<10}  F1={m['f1']:.3f}  n={m['support']}")
    else:
        summary["benchmark_evaluation"] = "NOT RUN"

    # ── Paper-ready conclusion ────────────────────────────────────
    if internal_acc and leakage:
        leakage_lvl = leakage['leakage_level']
        acc_drop = (original_random_acc - internal_acc) * 100
        if acc_drop < 2:
            conclusion = (
                f"pHash group-aware split confirmed {leakage_lvl} residual leakage. "
                f"The accuracy drop of {acc_drop:.1f}pp from random split "
                f"({original_random_acc*100:.1f}% → {internal_acc*100:.1f}%) suggests "
                f"the model learned genuine visual features, not just augmentation artefacts. "
                f"The {internal_acc*100:.1f}% figure is defensible for publication."
            )
        else:
            conclusion = (
                f"pHash group-aware split revealed {leakage_lvl} leakage. "
                f"Accuracy dropped {acc_drop:.1f}pp ({original_random_acc*100:.1f}% → "
                f"{internal_acc*100:.1f}%), confirming augmented variants were leaking "
                f"across the random split. The corrected {internal_acc*100:.1f}% is the "
                f"honest reportable figure."
            )
    else:
        conclusion = "Awaiting training completion and benchmark data."

    summary["paper_conclusion"] = conclusion

    # Save
    os.makedirs(os.path.dirname(SUMMARY_OUT), exist_ok=True)
    with open(SUMMARY_OUT, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  CONCLUSION")
    print(f"    {conclusion}")
    print(f"\n  Report saved: {SUMMARY_OUT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
