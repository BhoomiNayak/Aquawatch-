"""
verify_metrics.py
=================
Reproducibility verifier (audit Deliverable 6). Recomputes every headline paper
metric directly from the saved source-of-truth files and compares against the
manuscript-claimed values, printing PASS/FAIL per claim. Read-only: it does not
modify any data, model, or result file.

Sources of truth:
  datasets/local_benchmark/indian_validation_set.csv   (labels + annotators)
  reports/benchmark_probs.csv                           (cached classifier probs)
  reports/ablation_results_local.json                  (ablation metrics)
  reports/threshold_calibration.json                   (calibration metrics)
  reports/sentinel_lake_summary.csv                    (NDCI per lake)
  models/*.pt                                          (checkpoint metadata)

Usage:
  cd backend
  python scripts/verify_metrics.py
"""

from __future__ import annotations
import csv, json, os, collections
import numpy as np

BASE = os.path.dirname(os.path.dirname(__file__))
BENCH = os.path.join(BASE, "datasets", "local_benchmark", "indian_validation_set.csv")
PROBS = os.path.join(BASE, "reports", "benchmark_probs.csv")
ABL = os.path.join(BASE, "reports", "ablation_results_local.json")
THR = os.path.join(BASE, "reports", "threshold_calibration.json")
SENT = os.path.join(BASE, "reports", "sentinel_lake_summary.csv")

_checks = []
def check(name, got, expected, tol=0.01):
    ok = abs(float(got) - float(expected)) <= tol
    _checks.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} expected~={expected}")


def fleiss(items, cats):
    N, n = len(items), len(items[0])
    p_j = {c: 0 for c in cats}
    for it in items:
        for c in cats:
            p_j[c] += it.count(c)
    for c in cats:
        p_j[c] /= (N * n)
    P = [(sum(it.count(c) ** 2 for c in cats) - n) / (n * (n - 1)) for it in items]
    Pbar, Pe = sum(P) / N, sum(v * v for v in p_j.values())
    return (Pbar - Pe) / (1 - Pe)


def main():
    print("=" * 64)
    print("AquaWatch metric verification (recomputed vs paper claims)")
    print("=" * 64)

    # ---- Benchmark labels ----
    print("\n[Benchmark] datasets/local_benchmark/indian_validation_set.csv")
    rows = list(csv.DictReader(open(BENCH)))
    dist = collections.Counter(int(r["consensus_label"]) for r in rows)
    check("N unique images", len(set(r["image_id"] for r in rows)), 200, 0)
    check("Low count", dist[0], 71, 0)
    check("Moderate count", dist[1], 75, 0)
    check("High count", dist[2], 54, 0)
    base = sum(1 for r in rows if int(r["consensus_label"]) > 0) / len(rows)
    check("Binary base rate", round(base, 3), 0.645)
    three = [[int(r["annotator_1"]), int(r["annotator_2"]), int(r["annotator_3"])] for r in rows]
    check("Fleiss kappa (3-class)", round(fleiss(three, [0, 1, 2]), 3), 0.757)
    binz = [[0 if x == 0 else 1 for x in it] for it in three]
    check("Fleiss kappa (binary)", round(fleiss(binz, [0, 1]), 3), 0.795)

    # ---- OOD probabilities ----
    print("\n[OOD] reports/benchmark_probs.csv")
    pr = list(csv.DictReader(open(PROBS)))
    p = np.array([float(x["p_polluted"]) for x in pr])
    y = np.array([int(x["gt_binary"]) for x in pr])
    g3 = np.array([int(x["gt3"]) for x in pr])
    try:
        from sklearn.metrics import roc_auc_score
        check("ROC-AUC", round(roc_auc_score(y, p), 3), 0.49, 0.02)
    except ImportError:
        print("  [SKIP] sklearn missing for AUC")
    check("Pearson corr(p,severity)", round(float(np.corrcoef(p, g3)[0, 1]), 3), -0.12, 0.02)
    try:
        from scipy.stats import spearmanr
        sp = float(spearmanr(p, g3).correlation)
        print(f"  [INFO] Spearman corr(p,severity) = {sp:.3f} "
              f"(ordinal-appropriate; ~0 => no monotonic relation)")
    except ImportError:
        pass
    pred = (p >= 0.5).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    check("tau=0.5 sensitivity", round(tp / (tp + fn), 3), 0.930)
    check("tau=0.5 specificity", round(tn / (tn + fp), 3), 0.028)

    # ---- Ablation ----
    print("\n[Ablation] reports/ablation_results_local.json")
    ab = json.load(open(ABL))
    want = {"CV-only": (0.565, 0.718), "EfficientNet-only": (0.61, 0.755),
            "YOLO-only": (0.438, 0.417), "Ensemble (baseline_v1)": (0.645, 0.783)}
    for m in ab["binary_framing"]:
        if m["model"] in want:
            a, f = want[m["model"]]
            check(f"{m['model']} accuracy", m["accuracy"], a)
            check(f"{m['model']} F1", m["f1_polluted"], f)

    # ---- Threshold calibration ----
    print("\n[Calibration] reports/threshold_calibration.json")
    th = json.load(open(THR))
    check("global ROC-AUC", th["global_roc_auc"], 0.49, 0.02)
    s = th["cv"]["summary"]
    check("calibrated accuracy (CV mean)", s["accuracy"]["mean"], 0.55)
    check("calibrated specificity (CV mean)", s["specificity"]["mean"], 0.324, 0.02)
    check("OOD gap vs internal", th["ood_gap_vs_internal"], 0.449, 0.02)

    # ---- Sentinel NDCI ----
    print("\n[Sentinel] reports/sentinel_lake_summary.csv")
    sent = {r["lake"]: r for r in csv.DictReader(open(SENT))}
    check("Hussain Sagar median NDCI", float(sent["Hussain Sagar"]["ndci_median"]), 0.263, 0.01)
    check("Ulsoor median NDCI", float(sent["Ulsoor Lake"]["ndci_median"]), 0.346, 0.01)

    # ---- Checkpoint metadata (deployment consistency) ----
    print("\n[Checkpoints] models/*.pt (deployment consistency)")
    try:
        import torch
        prod = torch.load(os.path.join(BASE, "models", "efficientnet_water_quality.pt"),
                          map_location="cpu", weights_only=False)
        ga = torch.load(os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt"),
                        map_location="cpu", weights_only=False)
        print(f"  [INFO] production checkpoint val_acc={prod.get('val_acc'):.4f} "
              f"class_to_idx={prod.get('class_to_idx')} split={prod.get('split')}")
        print(f"  [INFO] evaluated  checkpoint val_acc={ga.get('val_acc'):.4f} "
              f"class_to_idx={ga.get('class_to_idx')} split={ga.get('split')}")
        same = prod.get("split") == ga.get("split")
        print(f"  [{'PASS' if not same else 'WARN'}] production != evaluated checkpoint "
              f"(paper metrics use the group-aware model; API serves the other)")
    except Exception as e:
        print(f"  [SKIP] checkpoint load: {e}")

    print("\n" + "=" * 64)
    n_pass = sum(_checks)
    print(f"RESULT: {n_pass}/{len(_checks)} numeric checks PASS")
    print("=" * 64)


if __name__ == "__main__":
    main()
