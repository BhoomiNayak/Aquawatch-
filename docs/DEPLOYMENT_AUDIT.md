# Deployment Consistency Audit — EfficientNet checkpoint (read-only)

**Status:** investigation only. No production code, checkpoints, or inference
behaviour were modified. This document records evidence and proposes a patch +
isolated test plan for approval.

## 1. The two checkpoints

| | Production checkpoint | Evaluated checkpoint |
|---|---|---|
| File | `backend/models/efficientnet_water_quality.pt` | `backend/models/efficientnet_water_quality_group_aware.pt` |
| `val_acc` (stored) | 0.9975 | 0.99888 |
| `split` | `None` (original random split) | `group_aware_phash` |
| `class_to_idx` (stored) | `{'bad': 0, 'good': 1}` (class→idx, str keys) | `{0: 'bad', 1: 'good'}` (idx→class, int keys) |
| Used by | **production API** (`app/api/reports.py`) | **all evaluation** (ablation, calibration, benchmark, prediction) |
| Paper metrics? | No | **Yes** — every reported classifier/ensemble number |

Evidence: `torch.load(...)` metadata (recorded in `scripts/verify_metrics.py`
output); grep of `efficientnet_water_quality*.pt` across `backend/**/*.py`.

## 2. Inference interface comparison

Both training paths use `CLASS_MAP {"bad":0, "good":1}`, so **index 0 = bad** in
both checkpoints' logits. Architecture is identical: `efficientnet_b0` with head
`Sequential(Dropout(0.3), Linear(in_features, 2))`. Preprocessing is identical
in the production and evaluation paths: `Resize((224,224))` → `ToTensor` →
`Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])`.

The **only** incompatibility is how the label-string map is reconstructed:

- `app/api/reports.py` (production) uses a single-format inversion:
  ```python
  _eff_idx_to_class = {v: k for k, v in checkpoint['class_to_idx'].items()}
  ...
  pred_class = _eff_idx_to_class[predicted.item()]   # expects int keys 0/1
  bad_probability = probs[0][0]                       # assumes index 0 = bad
  ```
  - Production checkpoint `{'bad':0,'good':1}` → inversion `{0:'bad',1:'good'}` → `pred_class = map[0/1]` works; `probs[0][0]` = P(bad) correct.
  - Group-aware checkpoint `{0:'bad',1:'good'}` → inversion `{'bad':0,'good':1}` → `pred_class = map[0]` → **`KeyError: 0`** (verified).

- `scripts/ablation_harness.py` and `scripts/calibrate_threshold.py` use a
  **format-robust** loader that inspects the key type:
  ```python
  sk = next(iter(c2i.keys()))
  if isinstance(sk, int) or str(sk).isdigit():
      idx_to_class = {int(k): v for k, v in c2i.items()}
  else:
      idx_to_class = {int(v): k for k, v in c2i.items()}
  ```
  This handles both orientations, which is why the evaluation scripts run on the
  group-aware checkpoint but the production API would crash on it.

## 3. Consequences

- The deployed system does **not** serve the model the paper evaluates.
- The production checkpoint's own 0.9975 was measured on the original **random
  split** (leakage-prone), so it is not a trustworthy accuracy figure.
- The ablation "Ensemble" numbers use the group-aware classifier; the deployed
  ensemble uses the other checkpoint — so deployed behaviour ≠ evaluated behaviour.

## 4. Proposed patch (NOT applied — for approval)

In `app/api/reports.py::_load_efficientnet`, (a) adopt the robust mapping and
(b) make the bad-class index explicit rather than hard-coding 0; optionally make
the checkpoint path configurable so the evaluated model can be served:

```python
# checkpoint path (env-overridable; default = evaluated group-aware model)
model_path = os.environ.get(
    "EFFICIENTNET_CKPT",
    os.path.join(BASE, "models", "efficientnet_water_quality_group_aware.pt"))
...
c2i = checkpoint["class_to_idx"]
sk = next(iter(c2i.keys()))
if isinstance(sk, int) or str(sk).isdigit():
    idx_to_class = {int(k): v for k, v in c2i.items()}      # idx -> class
else:
    idx_to_class = {int(v): k for k, v in c2i.items()}
class_to_idx = {v: k for k, v in idx_to_class.items()}
_bad_idx = class_to_idx["bad"]
...
pred_class = idx_to_class[int(predicted.item())]
bad_probability = float(probs[0][_bad_idx])                 # not hard-coded 0
```

Risk: switching the served checkpoint changes production predictions and the
composite/ensemble scores users see. This is a deployment-behaviour change and
must be gated on the test plan below and explicit approval.

## 5. Isolated compatibility test plan (no production change)

Create `backend/scripts/test_ckpt_compatibility.py` (proposed) that:

1. Loads the group-aware checkpoint with the robust loader in a standalone
   process (does not import or mutate `reports.py`).
2. Runs inference on the 200 benchmark images with the exact production
   preprocessing.
3. Asserts: (a) no `KeyError`; (b) `idx_to_class == {0:'bad',1:'good'}`;
   (c) `bad` index resolves to logit index 0.
4. Cross-checks the derived `P(polluted)=probs[bad_idx]` against the cached
   `reports/benchmark_probs.csv` (must match within 1e-4) to prove the
   standalone path reproduces the evaluated probabilities.
5. Runs the **production** checkpoint through the same path and reports a
   confusion matrix of production-vs-group-aware predicted labels on the 200
   images, quantifying how much deployed behaviour would change.

Success criteria: (a)–(d) hold and the behaviour-change delta is reviewed and
accepted before any change to `reports.py` or the served checkpoint.

## 6. Recommendation

Until approved and tested: **document** in the manuscript (done — §V item 8)
that reported metrics use the group-aware checkpoint while the deployed API
currently serves a different one. Do not claim deployed accuracy equals the
evaluated 99.89 %/ablation numbers.
