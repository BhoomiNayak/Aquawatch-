"""
ablation_harness.py
===================
THE evaluation harness. Fires the instant labeled data is available.

Answers the core scientific questions empirically:
  - How accurate is each component ALONE on real Indian water images?
  - Does the ensemble beat the best single model?
  - Is the complexity (CV + YOLO + EfficientNet) justified, or does one model win?

Produces the ablation table that goes straight into the paper.

--------------------------------------------------------------------
PREREQUISITE: labeled ground truth CSV.
--------------------------------------------------------------------
Expected: datasets/IndianWaterDataset/image_metadata.csv with a final
label column. Accepts EITHER:
  (a) a 'final_label' column (0/1/2 majority vote), OR
  (b) annotator_1/2/3 columns (script computes majority vote itself).

Label scale: 0=Low(clean), 1=Moderate, 2=High(polluted)

--------------------------------------------------------------------
EVALUATION MODES
--------------------------------------------------------------------
The system is natively 3-class (Low/Moderate/High) for CV, but
EfficientNet is binary (good/bad) and YOLO is (clean/turbid/polluted).
To compare fairly we evaluate in TWO framings:

  BINARY framing  (clean vs polluted):
      ground truth: 0 -> clean(0),  1&2 -> polluted(1)
      CV:           low -> clean, moderate&high -> polluted
      EfficientNet: good -> clean, bad -> polluted
      YOLO:         clean -> clean, turbid&polluted -> polluted

  THREE-CLASS framing (Low/Moderate/High):
      only CV composite + ensemble produce 3 levels; reported separately.

--------------------------------------------------------------------
USAGE:
    cd backend
    python scripts/ablation_harness.py

OUTPUTS:
    reports/ablation_results.json     — full metrics, all models, both framings
    reports/ablation_table.txt        — paper-ready table
"""

import os
import sys
import csv
import json
import glob
import io
import argparse
import logging
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("MPLCONFIGDIR", "C:/tmp/mpl")

import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image

from app.services.cv_analysis import analyze_image
from app.services.risk_scoring import calculate_risk_from_analysis, classify_risk_level
from app.services.yolo_detector import detect_water_quality_local

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ablation")

# ── Paths (defaults; overridable via CLI) ────────────────────────────────
# Default target is the scraped test set. The curated, human-labeled Indian
# benchmark lives under datasets/local_benchmark — pass --benchmark local to
# target it (IND_*.jpg images + consensus_label CSV).
IMG_DIR   = os.path.join(BASE, "datasets", "IndianWaterDataset", "indian_test_set_200")
META_CSV  = os.path.join(BASE, "datasets", "IndianWaterDataset", "image_metadata.csv")
EFF_MODEL = os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt")
OUT_JSON  = os.path.join(BASE, "reports", "ablation_results.json")
OUT_TXT   = os.path.join(BASE, "reports", "ablation_table.txt")

# Filename column and image glob pattern (adjusted per benchmark).
FNAME_COL = "filename"
IMG_GLOB  = "*.jpg"


# ── Ground-truth loading ────────────────────────────────────────────────
def load_ground_truth():
    """
    Returns {filename: label_int(0/1/2)} from metadata CSV.
    Priority: 'consensus_label' > 'final_label' > majority vote of
    annotator_1/2/3. Returns (labels_dict, note).
    """
    if not os.path.exists(META_CSV):
        return None, "metadata CSV not found"

    labels = {}
    rows = []
    with open(META_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return None, "metadata CSV empty"

    cols = rows[0].keys()
    # Filename column auto-detect: 'filename' (scraped set) or 'image_id'
    # (local_benchmark set, values already include the .jpg extension).
    fname_col = FNAME_COL if FNAME_COL in cols else (
        "filename" if "filename" in cols else (
            "image_id" if "image_id" in cols else None))
    if fname_col is None:
        return None, "no filename/image_id column in CSV"
    label_col = "consensus_label" if "consensus_label" in cols else (
        "final_label" if "final_label" in cols else None)
    has_annot = all(c in cols for c in ("annotator_1", "annotator_2", "annotator_3"))

    n_labeled = 0
    for row in rows:
        fname = row[fname_col]
        label = None

        if label_col and row.get(label_col, "").strip() != "":
            try:
                label = int(float(row[label_col]))
            except ValueError:
                label = None

        if label is None and has_annot:
            votes = []
            for c in ("annotator_1", "annotator_2", "annotator_3"):
                v = row.get(c, "").strip()
                if v != "" and v.upper() != "EXCLUDE":
                    try:
                        votes.append(int(float(v)))
                    except ValueError:
                        pass
            if votes:
                # majority vote; tie → highest (safety-first)
                cnt = Counter(votes)
                top = max(cnt.values())
                candidates = [k for k, v in cnt.items() if v == top]
                label = max(candidates)

        if label is not None and label in (0, 1, 2):
            labels[fname] = label
            n_labeled += 1

    src = label_col if label_col else "majority vote"
    note = f"{n_labeled} labeled images ({src})"
    return (labels if n_labeled > 0 else None), note


# ── Model loading ─────────────────────────────────────────────────────────
def load_efficientnet(device):
    if not os.path.exists(EFF_MODEL):
        return None, None
    ckpt = torch.load(EFF_MODEL, map_location=device, weights_only=False)
    model = models.efficientnet_b0(weights=None)
    model.classifier = nn.Sequential(nn.Dropout(0.3),
                                     nn.Linear(model.classifier[1].in_features, 2))
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval().to(device)
    c2i = ckpt["class_to_idx"]
    sk = next(iter(c2i.keys()))
    if isinstance(sk, int) or (isinstance(sk, str) and str(sk).isdigit()):
        idx_to_class = {int(k): v for k, v in c2i.items()}
    else:
        idx_to_class = {int(v): k for k, v in c2i.items()}
    return model, idx_to_class


# ── Per-model predictions (binary: 0=clean, 1=polluted) ──────────────────
def cv_binary(cv_level_name):
    return 0 if cv_level_name == "low" else 1

def cv_threeclass(cv_level_name):
    return {"low": 0, "moderate": 1, "high": 2}[cv_level_name]

def eff_binary(eff_label):
    return 0 if eff_label == "good" else 1

def yolo_binary(yolo_pred, available):
    if not available:
        return None
    return 0 if yolo_pred == "clean" else 1

def gt_binary(gt3):
    return 0 if gt3 == 0 else 1


# ── Metric computation ────────────────────────────────────────────────────
def binary_metrics(y_true, y_pred, name):
    from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                                 confusion_matrix)
    # Filter out None predictions (e.g. YOLO no-detection)
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if p is not None]
    coverage = len(pairs) / len(y_true) if y_true else 0
    if not pairs:
        return {"model": name, "coverage": 0, "n": 0, "note": "no predictions"}
    yt, yp = zip(*pairs)
    acc = accuracy_score(yt, yp)
    p, r, f1, _ = precision_recall_fscore_support(yt, yp, average="binary",
                                                  pos_label=1, zero_division=0)
    cm = confusion_matrix(yt, yp, labels=[0, 1]).tolist()
    return {
        "model": name,
        "n": len(pairs),
        "coverage": round(coverage, 3),
        "accuracy": round(float(acc), 4),
        "precision_polluted": round(float(p), 4),
        "recall_polluted": round(float(r), 4),
        "f1_polluted": round(float(f1), 4),
        "confusion_matrix": cm,  # [[TN,FP],[FN,TP]]
    }

def threeclass_metrics(y_true, y_pred, name):
    from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                                 confusion_matrix)
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if p is not None]
    if not pairs:
        return {"model": name, "n": 0}
    yt, yp = zip(*pairs)
    acc = accuracy_score(yt, yp)
    p, r, f1, _ = precision_recall_fscore_support(yt, yp, average="macro",
                                                  zero_division=0)
    cm = confusion_matrix(yt, yp, labels=[0, 1, 2]).tolist()
    return {
        "model": name,
        "n": len(pairs),
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(f1), 4),
        "confusion_matrix": cm,
    }


def main():
    global IMG_DIR, META_CSV, FNAME_COL, OUT_JSON, OUT_TXT

    ap = argparse.ArgumentParser(description="AquaWatch ablation harness")
    ap.add_argument("--benchmark", choices=["scraped", "local"], default="scraped",
                    help="'scraped' = IndianWaterDataset/indian_test_set_200 (default); "
                         "'local' = curated human-labeled local_benchmark set")
    ap.add_argument("--img-dir", default=None, help="override image directory")
    ap.add_argument("--meta-csv", default=None, help="override metadata CSV")
    args = ap.parse_args()

    if args.benchmark == "local":
        IMG_DIR  = os.path.join(BASE, "datasets", "local_benchmark", "images")
        META_CSV = os.path.join(BASE, "datasets", "local_benchmark",
                                "indian_validation_set.csv")
        OUT_JSON = os.path.join(BASE, "reports", "ablation_results_local.json")
        OUT_TXT  = os.path.join(BASE, "reports", "ablation_table_local.txt")

    if args.img_dir:
        IMG_DIR = args.img_dir
    if args.meta_csv:
        META_CSV = args.meta_csv

    print("=" * 70)
    print("AquaWatch — ABLATION HARNESS")
    print("=" * 70)
    print(f"  Images : {IMG_DIR}")
    print(f"  Labels : {META_CSV}")

    # 1. Ground truth
    gt, note = load_ground_truth()
    if gt is None:
        print(f"\n  NO LABELS YET — {note}")
        print("  This harness is READY. It will run the moment labels exist.")
        print("  Annotators must fill annotator_1/2/3 (0/1/2) in:")
        print(f"    {META_CSV}")
        print("\n  Once labeled, re-run: python scripts/ablation_harness.py")
        print("=" * 70)
        return

    log.info(f"Ground truth: {note}")

    # 2. Load models
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    eff_model, idx_to_class = load_efficientnet(device)
    tfm = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    # 3. Run all models on every labeled image
    log.info("Running all models on labeled images...")
    per_image = []
    files = sorted(glob.glob(os.path.join(IMG_DIR, IMG_GLOB)))

    for i, path in enumerate(files):
        fname = os.path.basename(path)
        if fname not in gt:
            continue
        if (i + 1) % 25 == 0:
            log.info(f"  {i+1}/{len(files)}")
        try:
            with open(path, "rb") as fh:
                b = fh.read()
            cv = analyze_image(b)
            risk = calculate_risk_from_analysis(cv)
            cv_level = classify_risk_level(risk["composite_score"])

            # EfficientNet
            img = Image.open(io.BytesIO(b)).convert("RGB")
            x = tfm(img).unsqueeze(0).to(device)
            with torch.no_grad():
                probs = torch.softmax(eff_model(x), dim=1)
                conf, pred = torch.max(probs, 1)
            eff_label = idx_to_class[pred.item()]
            eff_bad_prob = float(probs[0][0].item())  # idx0 = bad

            # YOLO
            yolo = detect_water_quality_local(b)

            # Ensemble (baseline_v1 fusion — mirrors reports.py)
            ens_score = risk["composite_score"]
            if eff_label == "bad" and conf.item() > 0.70:
                ens_score = min(100, ens_score + eff_bad_prob * 25)
                if yolo["yolo_available"]:
                    if yolo["prediction"] == "polluted":
                        ens_score = min(100, ens_score + yolo["confidence"] * 30)
                    elif yolo["prediction"] == "turbid":
                        ens_score = min(100, ens_score + yolo["confidence"] * 15)
            ens_level = classify_risk_level(ens_score)

            per_image.append({
                "filename": fname,
                "gt3": gt[fname],
                "cv_level": cv_level,
                "eff_label": eff_label,
                "yolo_pred": yolo["prediction"] if yolo["yolo_available"] else None,
                "yolo_avail": yolo["yolo_available"],
                "ens_level": ens_level,
            })
        except Exception as e:
            log.warning(f"  Failed {fname}: {e}")

    n = len(per_image)
    log.info(f"Evaluated {n} labeled images")

    # 4. Build prediction vectors
    gt3   = [r["gt3"] for r in per_image]
    gt2   = [gt_binary(g) for g in gt3]

    cv_b   = [cv_binary(r["cv_level"]) for r in per_image]
    eff_b  = [eff_binary(r["eff_label"]) for r in per_image]
    yolo_b = [yolo_binary(r["yolo_pred"], r["yolo_avail"]) for r in per_image]
    ens_b  = [cv_binary(r["ens_level"]) for r in per_image]

    cv_3   = [cv_threeclass(r["cv_level"]) for r in per_image]
    ens_3  = [cv_threeclass(r["ens_level"]) for r in per_image]

    # 5. Metrics — BINARY framing
    binary_results = [
        binary_metrics(gt2, cv_b,   "CV-only"),
        binary_metrics(gt2, eff_b,  "EfficientNet-only"),
        binary_metrics(gt2, yolo_b, "YOLO-only"),
        binary_metrics(gt2, ens_b,  "Ensemble (baseline_v1)"),
    ]

    # 6. Metrics — THREE-CLASS framing (only CV + ensemble)
    threeclass_results = [
        threeclass_metrics(gt3, cv_3,  "CV-only (3-class)"),
        threeclass_metrics(gt3, ens_3, "Ensemble (3-class)"),
    ]

    # 7. GT distribution
    gt_dist = dict(Counter(gt3))

    report = {
        "n_labeled": n,
        "gt_distribution_3class": gt_dist,
        "gt_distribution_binary": dict(Counter(gt2)),
        "binary_framing": binary_results,
        "threeclass_framing": threeclass_results,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(report, f, indent=2)

    # 8. Paper-ready table
    lines = []
    lines.append("=" * 70)
    lines.append("ABLATION RESULTS — Indian Water Benchmark")
    lines.append("=" * 70)
    lines.append(f"Labeled images: {n}")
    lines.append(f"GT distribution (3-class): Low={gt_dist.get(0,0)} "
                 f"Moderate={gt_dist.get(1,0)} High={gt_dist.get(2,0)}")
    lines.append("")
    lines.append("BINARY FRAMING (clean vs polluted)")
    lines.append("-" * 70)
    lines.append(f"{'Model':<26}{'Acc':>7}{'Prec':>7}{'Rec':>7}{'F1':>7}{'Cov':>7}")
    lines.append("-" * 70)
    for m in binary_results:
        if m.get("n", 0) == 0:
            lines.append(f"{m['model']:<26}  (no predictions)")
            continue
        lines.append(f"{m['model']:<26}"
                     f"{m['accuracy']*100:>6.1f}%"
                     f"{m['precision_polluted']*100:>6.1f}%"
                     f"{m['recall_polluted']*100:>6.1f}%"
                     f"{m['f1_polluted']*100:>6.1f}%"
                     f"{m['coverage']*100:>6.0f}%")
    lines.append("")
    lines.append("THREE-CLASS FRAMING (Low / Moderate / High)")
    lines.append("-" * 70)
    lines.append(f"{'Model':<26}{'Acc':>7}{'MacroF1':>9}")
    lines.append("-" * 70)
    for m in threeclass_results:
        if m.get("n", 0) == 0:
            continue
        lines.append(f"{m['model']:<26}{m['accuracy']*100:>6.1f}%{m['macro_f1']*100:>8.1f}%")
    lines.append("")

    # 9. Verdict
    best_single = max(
        [m for m in binary_results if m["model"] != "Ensemble (baseline_v1)" and m.get("n")],
        key=lambda m: m["f1_polluted"]
    )
    ensemble = next(m for m in binary_results if m["model"] == "Ensemble (baseline_v1)")
    lines.append("VERDICT")
    lines.append("-" * 70)
    lines.append(f"Best single model: {best_single['model']} (F1={best_single['f1_polluted']*100:.1f}%)")
    lines.append(f"Ensemble:          F1={ensemble['f1_polluted']*100:.1f}%")
    delta = (ensemble["f1_polluted"] - best_single["f1_polluted"]) * 100
    if delta > 2:
        lines.append(f"-> Ensemble beats best single by {delta:.1f}pp (binary F1). "
                     f"But check WHETHER the gain is real skill or just base-rate bias "
                     f"(compare precision vs the polluted base rate).")
    elif delta < -2:
        lines.append(f"-> Ensemble is WORSE than {best_single['model']} by {-delta:.1f}pp. "
                     f"DROP the ensemble, ship the single model.")
    else:
        lines.append(f"-> Ensemble ~= best single (delta {delta:+.1f}pp). "
                     f"Complexity NOT justified -- prefer the simpler model.")

    # Base-rate sanity check: a constant "always polluted" classifier.
    _gtc = Counter(gt2)
    pol = _gtc.get(1, 0)
    tot = sum(_gtc.values()) or 1
    base = pol / tot
    lines.append(f"   Base rate (always-polluted) accuracy = {base*100:.1f}%. "
                 f"Any model near this is not actually discriminating clean water.")
    lines.append("=" * 70)

    table = "\n".join(lines)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(table)

    print("\n" + table)
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")


if __name__ == "__main__":
    main()
