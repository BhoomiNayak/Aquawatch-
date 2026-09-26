"""
calibrate_threshold.py
======================
Step 1 of the honest-validation methodology.

Question answered
-----------------
On the τ=0.5 default, EfficientNet collapses to "always polluted" on real
Indian water (specificity ~= 0). Does DOMAIN THRESHOLD RECALIBRATION recover
specificity, or is the model fundamentally not discriminating?

Method
------
1. Run EfficientNet-B0 once on the 200-image human-labeled benchmark
   (datasets/local_benchmark) and cache P(polluted) per image.
2. Collapse the 3-class consensus to BINARY:  Low(0) -> clean(0),
   Moderate/High(1,2) -> polluted(1).
3. 5-fold STRATIFIED cross-validation:
     - on each training fold, pick tau* maximizing Youden's J
       (Sensitivity + Specificity - 1) from the ROC curve;
     - freeze tau*, evaluate on the held-out fold.
4. Report per-fold and pooled out-of-fold (OOF) metrics with mean +/- std:
   Accuracy, Sensitivity, Specificity, F1, ROC-AUC.
5. Compare against:
     - the naive tau=0.5 baseline (the "always polluted" failure), and
     - the 99.9% internal pHash validation accuracy (the OOD gap).

Outputs
-------
    reports/benchmark_probs.csv         cached per-image probabilities + labels
    reports/threshold_calibration.json  full metrics
    reports/threshold_calibration.txt   paper-ready table

Usage
-----
    cd backend
    $env:MPLCONFIGDIR="C:/tmp/mpl"
    python scripts/calibrate_threshold.py
    python scripts/calibrate_threshold.py --recompute   # force re-inference
"""

import os
import sys
import csv
import json
import glob
import argparse
import logging

BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("calibrate")

# ── Paths ────────────────────────────────────────────────────────────────
IMG_DIR   = os.path.join(BASE, "datasets", "local_benchmark", "images")
META_CSV  = os.path.join(BASE, "datasets", "local_benchmark", "indian_validation_set.csv")
EFF_MODEL = os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt")
PROB_CSV  = os.path.join(BASE, "reports", "benchmark_probs.csv")
OUT_JSON  = os.path.join(BASE, "reports", "threshold_calibration.json")
OUT_TXT   = os.path.join(BASE, "reports", "threshold_calibration.txt")

INTERNAL_VAL_ACC = 0.9988   # EfficientNet group-aware pHash validation accuracy
N_SPLITS = 5
SEED = 42


# ── Ground truth ───────────────────────────────────────────────────────────
def load_labels():
    """{image_filename: (gt3, gt_binary)} from consensus_label."""
    with open(META_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    fcol = "image_id" if "image_id" in rows[0] else "filename"
    out = {}
    for r in rows:
        v = r.get("consensus_label", "").strip()
        if v == "":
            continue
        g3 = int(float(v))
        out[r[fcol]] = (g3, 0 if g3 == 0 else 1)
    return out


# ── Inference (cached) ──────────────────────────────────────────────────────
def compute_probabilities():
    """Run EfficientNet on all benchmark images -> P(polluted) per image."""
    import torch
    import torch.nn as nn
    from torchvision import transforms, models
    from PIL import Image

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")

    ckpt = torch.load(EFF_MODEL, map_location=device, weights_only=False)
    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(model.classifier[1].in_features, 2))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval().to(device)

    # Resolve which output index means "polluted" (bad).
    c2i = ckpt["class_to_idx"]
    sk = next(iter(c2i.keys()))
    if isinstance(sk, int) or str(sk).isdigit():
        idx_to_class = {int(k): v for k, v in c2i.items()}
    else:
        idx_to_class = {int(v): k for k, v in c2i.items()}
    polluted_idx = next(i for i, c in idx_to_class.items()
                        if str(c).lower() in ("bad", "polluted"))
    log.info(f"class map {idx_to_class}; polluted index = {polluted_idx}")

    tfm = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    labels = load_labels()
    rows = []
    files = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    log.info(f"Running inference on {len(files)} images...")
    for i, path in enumerate(files):
        fname = os.path.basename(path)
        if fname not in labels:
            continue
        g3, gb = labels[fname]
        try:
            img = Image.open(path).convert("RGB")
            x = tfm(img).unsqueeze(0).to(device)
            with torch.no_grad():
                p = torch.softmax(model(x), dim=1).cpu().numpy()[0]
            rows.append({"image_id": fname, "p_polluted": float(p[polluted_idx]),
                         "gt3": g3, "gt_binary": gb})
        except Exception as e:
            log.warning(f"skip {fname}: {e}")
        if (i + 1) % 50 == 0:
            log.info(f"  {i+1}/{len(files)}")

    os.makedirs(os.path.dirname(PROB_CSV), exist_ok=True)
    with open(PROB_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image_id", "p_polluted", "gt3", "gt_binary"])
        w.writeheader()
        w.writerows(rows)
    log.info(f"Cached {len(rows)} probabilities -> {PROB_CSV}")
    return rows


def load_probabilities(recompute=False):
    if not recompute and os.path.exists(PROB_CSV):
        with open(PROB_CSV, newline="") as f:
            rows = list(csv.DictReader(f))
        log.info(f"Loaded cached probabilities: {len(rows)} ({PROB_CSV})")
        return [{"image_id": r["image_id"], "p_polluted": float(r["p_polluted"]),
                 "gt3": int(r["gt3"]), "gt_binary": int(r["gt_binary"])} for r in rows]
    return compute_probabilities()


# ── Metrics ────────────────────────────────────────────────────────────────
def binary_scores(y_true, y_pred):
    """Return acc, sensitivity(recall+), specificity(recall-), f1(+)."""
    y_true = np.asarray(y_true); y_pred = np.asarray(y_pred)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    acc = (tp + tn) / max(1, len(y_true))
    sens = tp / max(1, tp + fn)                 # recall for polluted
    spec = tn / max(1, tn + fp)                 # recall for clean
    prec = tp / max(1, tp + fp)
    f1 = (2 * prec * sens / max(1e-9, prec + sens)) if (prec + sens) else 0.0
    return {"accuracy": acc, "sensitivity": sens, "specificity": spec,
            "f1": f1, "precision": prec, "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def youden_threshold(y, p):
    """tau* maximizing Youden's J = TPR - FPR over the ROC curve."""
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y, p)
    j = tpr - fpr
    k = int(np.argmax(j))
    tau = float(thr[k])
    # roc_curve can emit +inf as the first threshold; clamp to (0,1].
    if not np.isfinite(tau):
        tau = 1.0
    return tau, float(j[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true",
                    help="force re-inference instead of using cached probs")
    args = ap.parse_args()

    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score

    data = load_probabilities(recompute=args.recompute)
    p = np.array([d["p_polluted"] for d in data])
    y = np.array([d["gt_binary"] for d in data])
    n = len(y)
    n_pol = int(y.sum()); n_clean = n - n_pol
    base_rate = n_pol / n

    print("=" * 70)
    print("THRESHOLD CALIBRATION — EfficientNet on Indian benchmark (binary)")
    print("=" * 70)
    print(f"  N={n}  clean(Low)={n_clean}  polluted(Mod+High)={n_pol}  "
          f"base rate={base_rate*100:.1f}%")

    # Threshold-independent separability.
    global_auc = float(roc_auc_score(y, p))

    # ── Baseline: naive tau=0.5 (the observed failure) ──
    base_pred = (p >= 0.5).astype(int)
    base = binary_scores(y, base_pred)

    # ── 5-fold stratified CV with per-fold Youden threshold ──
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    fold_rows = []
    oof_pred = np.full(n, -1, dtype=int)   # out-of-fold predictions
    taus = []
    for fold, (tr, te) in enumerate(skf.split(p.reshape(-1, 1), y), 1):
        tau, jstat = youden_threshold(y[tr], p[tr])
        taus.append(tau)
        pred_te = (p[te] >= tau).astype(int)
        oof_pred[te] = pred_te
        m = binary_scores(y[te], pred_te)
        try:
            fold_auc = float(roc_auc_score(y[te], p[te]))
        except ValueError:
            fold_auc = float("nan")
        m.update({"fold": fold, "tau": tau, "youden_J_train": jstat,
                  "roc_auc": fold_auc, "n_test": int(len(te))})
        fold_rows.append(m)

    def agg(key):
        vals = [f[key] for f in fold_rows]
        return float(np.mean(vals)), float(np.std(vals))

    metrics_keys = ["accuracy", "sensitivity", "specificity", "f1", "roc_auc"]
    cv_summary = {k: {"mean": agg(k)[0], "std": agg(k)[1]} for k in metrics_keys}
    tau_mean, tau_std = float(np.mean(taus)), float(np.std(taus))

    # Pooled out-of-fold (each sample predicted exactly once).
    oof = binary_scores(y, oof_pred)

    ood_gap = INTERNAL_VAL_ACC - oof["accuracy"]

    report = {
        "n": n, "n_clean": n_clean, "n_polluted": n_pol,
        "base_rate": round(base_rate, 4),
        "global_roc_auc": round(global_auc, 4),
        "internal_val_accuracy": INTERNAL_VAL_ACC,
        "baseline_tau_0.5": {k: round(base[k], 4)
                             for k in ("accuracy", "sensitivity", "specificity",
                                       "f1", "precision")},
        "cv": {
            "n_splits": N_SPLITS,
            # tau kept at full-ish precision: the model saturates near 1.0, so
            # rounding to 4 dp would misleadingly print 1.0 for a ~0.99998 tau.
            "tau_mean": round(tau_mean, 6), "tau_std": round(tau_std, 6),
            "per_fold": [{kk: (round(vv, 6) if isinstance(vv, float) else vv)
                          for kk, vv in f.items()} for f in fold_rows],
            "summary": {k: {"mean": round(v["mean"], 4), "std": round(v["std"], 4)}
                        for k, v in cv_summary.items()},
        },
        "pooled_oof": {k: round(oof[k], 4)
                       for k in ("accuracy", "sensitivity", "specificity",
                                 "f1", "precision", "tp", "tn", "fp", "fn")},
        "ood_gap_vs_internal": round(ood_gap, 4),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # ── Paper-ready table ──
    L = []
    L.append("=" * 70)
    L.append("THRESHOLD CALIBRATION RESULTS — EfficientNet-B0, Indian benchmark")
    L.append("=" * 70)
    L.append(f"N={n}  clean(Low)={n_clean}  polluted(Mod+High)={n_pol}  "
             f"base rate={base_rate*100:.1f}%")
    L.append(f"Global ROC-AUC (threshold-independent): {global_auc:.4f}")
    L.append("")
    L.append("BASELINE  tau=0.50  (the observed 'always polluted' failure)")
    L.append("-" * 70)
    L.append(f"  Accuracy    {base['accuracy']*100:5.1f}%")
    L.append(f"  Sensitivity {base['sensitivity']*100:5.1f}%  (polluted recall)")
    L.append(f"  Specificity {base['specificity']*100:5.1f}%  (clean recall)")
    L.append(f"  F1          {base['f1']*100:5.1f}%")
    L.append("")
    L.append(f"CALIBRATED  {N_SPLITS}-fold CV, per-fold Youden's J   "
             f"(tau* = {tau_mean:.5f} +/- {tau_std:.5f})")
    L.append(f"  NOTE: tau* sits in the extreme upper tail (~{tau_mean:.5f}) because the")
    L.append(f"  model saturates P(polluted)->1.0 on most images; even the best Youden")
    L.append(f"  operating point yields J~0.05 (near chance). This is a symptom of the")
    L.append(f"  AUC~0.49 failure, not a usable threshold.")
    L.append("-" * 70)
    L.append(f"{'Metric':<14}{'Mean':>8}{'Std':>8}")
    for k in metrics_keys:
        s = cv_summary[k]
        L.append(f"{k:<14}{s['mean']*100:>7.1f}%{s['std']*100:>7.1f}%")
    L.append("")
    L.append("POOLED OUT-OF-FOLD (each image predicted once at its fold's tau*)")
    L.append("-" * 70)
    L.append(f"  Accuracy    {oof['accuracy']*100:5.1f}%")
    L.append(f"  Sensitivity {oof['sensitivity']*100:5.1f}%")
    L.append(f"  Specificity {oof['specificity']*100:5.1f}%")
    L.append(f"  F1          {oof['f1']*100:5.1f}%")
    L.append(f"  Confusion   TN={oof['tn']} FP={oof['fp']} FN={oof['fn']} TP={oof['tp']}")
    L.append("")
    L.append("OOD GAP")
    L.append("-" * 70)
    L.append(f"  Internal pHash val accuracy:  {INTERNAL_VAL_ACC*100:.1f}%")
    L.append(f"  Benchmark OOF accuracy:       {oof['accuracy']*100:.1f}%")
    L.append(f"  OOD drop:                     {ood_gap*100:.1f}pp")
    L.append("")
    L.append("READING")
    L.append("-" * 70)
    d_spec = (oof['specificity'] - base['specificity']) * 100
    L.append(f"  Recalibration changed specificity by {d_spec:+.1f}pp "
             f"({base['specificity']*100:.1f}% -> {oof['specificity']*100:.1f}%).")
    if global_auc < 0.60:
        L.append(f"  ROC-AUC {global_auc:.2f} ~ chance: the model is NOT separating clean")
        L.append(f"  from polluted on Indian water. Threshold tuning cannot fix a model")
        L.append(f"  that lacks discriminative signal -- report as a genuine OOD failure.")
    elif global_auc < 0.75:
        L.append(f"  ROC-AUC {global_auc:.2f}: weak-to-moderate separability. Recalibration")
        L.append(f"  rebalances errors but the ceiling is limited by the model itself.")
    else:
        L.append(f"  ROC-AUC {global_auc:.2f}: real separability exists; the tau=0.5 failure")
        L.append(f"  was a CALIBRATION problem, and recalibration recovers usable accuracy.")
    L.append("=" * 70)
    table = "\n".join(L)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(table)

    print("\n" + table)
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")
    print(f"Saved: {PROB_CSV}")


if __name__ == "__main__":
    main()
