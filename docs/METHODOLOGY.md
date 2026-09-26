# AquaWatch: Methodology for a Cross-Modal Citizen-Science Water-Quality Triage System

## 1. Overview and contributions

AquaWatch is a two-layer system for monitoring urban water-body health:

1. **Ground layer** — citizens submit a geotagged photo; a server-side pipeline (classical computer vision + a deep classifier) produces a risk score.
2. **Satellite layer** — Sentinel-2 imagery (via Google Earth Engine) provides an **independent** physical corroboration signal (NDCI, a chlorophyll/eutrophication proxy) for water bodies large enough to resolve.

The paper's contributions are deliberately framed around **honest findings**, not a headline accuracy number:

- **C1.** A curated, human-annotated Indian water benchmark (N=200) with substantial inter-rater agreement.
- **C2.** Empirical evidence of a severe **out-of-distribution (OOD) collapse**: a classifier with ~99.9% in-distribution validation accuracy degrades to chance-level discrimination on real Indian water.
- **C3.** A demonstration that **post-hoc threshold recalibration is insufficient** to repair a model that lacks discriminative signal OOD.
- **C4.** A **cross-modal corroboration** result: Sentinel-2 NDCI separates eutrophic urban lakes from clean-reference controls where the ground classifier fails.

---

## 2. Datasets

| Dataset | Size | Labels | Origin | Role | License status |
|---|---|---|---|---|---|
| EyeOnWater | 22,376 (12,357 good / 10,019 bad) | binary clean/polluted | global citizen science | train classifier | research-use (not redistributed) |
| Indian benchmark (`local_benchmark`) | 200 | 3-class severity + consensus | curated Indian water bodies | **evaluation only** | image provenance to be documented |
| Pollution-type set | 223 (8 categories) | pollution type | Wikimedia/Flickr | CV-detector validation | **CC, fully attributed** |
| River segmentation (Roboflow) | 949 (665/189/95) | clean/turbid/polluted + masks | Indonesian rivers | train YOLO | CC-BY-4.0 |

Four different label schemes across four datasets; every training source differs in distribution and label taxonomy from the evaluation benchmark. **There is no Indian training data with severity labels** — the 200-image benchmark is held out strictly for evaluation. This train/test mismatch is not a defect to hide; it is the substrate of the OOD study (C2).

### 2.1 Benchmark annotation

The 200 images were independently labelled by three annotators on a 3-class severity scale (0 = Low, 1 = Moderate, 2 = High); the consensus label is the per-image majority vote (100% of rows resolvable, no three-way splits). Class distribution: **71 Low / 75 Moderate / 54 High**.

Inter-rater agreement (Fleiss' kappa):
- 3-class severity: kappa = 0.757
- binary (Low vs Moderate+High): kappa = 0.795

Both exceed the pre-registered kappa > 0.6 threshold ("substantial agreement"), so binary is adopted as the primary task and severity as a secondary (reported but not claimed).

### 2.2 Licensed benchmark collection

Because Google-scraped images carry no license metadata, a Wikimedia Commons collector was implemented that retrieves only free-licensed files (CC0 / public-domain / CC-BY / CC-BY-SA) and records license, author, and source URL per image. This produces the redistributable subset for publication; unknown-license images are used for internal evaluation only and reported with per-image source URLs for reproducibility.

---

## 3. Ground-level pipeline

### 3.1 Classical CV (7-factor)

Each image is analysed with OpenCV for seven factors: Forel-Ule colorimetry, algae detection, foam detection, turbidity, oil-sheen (rainbow + thick-slick), colour abnormality, and surface debris. A weighted composite (weights: turbidity 0.18, foam 0.18, debris 0.17, algae 0.15, colour-abnormality 0.15, Forel-Ule 0.10, oil 0.07) maps to a 0-100 risk score, classified Low (<=15) / Moderate (<=35) / High (>35).

### 3.2 Deep classifier

EfficientNet-B0 (ImageNet-initialised, 2-class head) fine-tuned on EyeOnWater.

**Data-leakage control.** To prevent near-duplicate leakage between train/val, images were clustered by perceptual hash (pHash) and split **group-aware**: 20,907 clusters from 22,376 images (~97% singletons); minimum cross-split Hamming distance = 12 (leakage audit: none). On this leakage-controlled split the model reaches **val accuracy 0.9988**.

### 3.3 Secondary detector

YOLOv8n-seg trained on the Indonesian river segmentation set (mAP@50 = 0.836 in-domain). Retained in experiments for ablation; **dropped from the production scoring path** (see 4.3).

---

## 4. Experimental protocol and results

All evaluation is on the held-out Indian benchmark (N=200). Binary framing: Low -> clean (0), Moderate+High -> polluted (1). Base rate = 64.5% polluted.

### 4.1 Ablation (binary framing)

| Model | Accuracy | Precision | Recall | F1 | Coverage |
|---|---|---|---|---|---|
| CV-only | 56.5% | 61.7% | 86.1% | 71.8% | 100% |
| EfficientNet-only | 61.0% | 63.5% | 93.0% | 75.5% | 100% |
| YOLO-only | 43.8% | 68.0% | 30.1% | 41.7% | 84.5% |
| Ensemble | 64.5% | 64.6% | 99.2% | 78.3% | 100% |

Three-class framing: CV-only 32.0% (macro-F1 22.8%); Ensemble 27.0% (macro-F1 18.6%) - both at or below the 37.5% majority-class baseline.

**Interpretation.** The ensemble's accuracy (64.5%) equals the base rate, with precision ~= base rate and recall 99.2% - i.e. it predicts "polluted" almost always. The F1 "gain" over the best single model is recall inflation from majority-class bias, **not** discriminative skill. Severity grading fails OOD.

### 4.2 Threshold recalibration (does calibration fix it?)

Protocol: run EfficientNet once, cache P(polluted); 5-fold stratified CV; on each training fold select tau* maximising **Youden's J** (J = sensitivity + specificity - 1); freeze and evaluate on the held-out fold.

- Threshold-independent **ROC-AUC = 0.49** (chance).
- Point-biserial correlation between P(polluted) and true severity = **-0.116** (weakly *inverted*).
- tau=0.5 baseline: acc 61.0%, sensitivity 93.0%, **specificity 2.8%**.
- Calibrated (tau* ~= 0.99999): acc 55.0% +/- 3.5%, sensitivity 67.5%, specificity 32.4%, F1 65.8%.
- **OOD gap: 99.9% (internal) -> 55.0% (benchmark OOF) = 44.9 pp.**

A qualitative check confirms the inversion: the 10 images the model is *most confident are clean* contain 5 High / 3 Moderate / 2 Low; the 10 it is *most confident are polluted* contain 7 Low (including pristine high-altitude lakes).

**Conclusion (C3).** With ROC-AUC ~= 0.5, no threshold exists that recovers useful accuracy. Recalibration only trades sensitivity for specificity along a diagonal ROC. The failure is representational, not a calibration artifact - the model lacks transferable discriminative signal on Indian water. The fix requires in-domain training data, not post-hoc tuning.

### 4.3 CV-detector validation

On the CC-licensed pollution-type set, 4/8 categories align with the intended detectors; turbidity and colour-abnormality dominate and can mask type-specific signals (debris under-sensitive on garbage/plastic). Reported as a component-level diagnostic.

---

## 5. Satellite corroboration layer

### 5.1 Indices

Sentinel-2 L2A (`COPERNICUS/S2_SR_HARMONIZED`), per-pixel cloud/shadow masking via the SCL band (classes {1,3,8,9,10,11} removed).

- Water mask (McFeeters NDWI): NDWI = (B3 - B8) / (B3 + B8) > 0
- Chlorophyll proxy (NDCI): NDCI = (B5 - B4) / (B5 + B4), averaged over water-masked pixels (20 m scale).

**No in-situ chlorophyll exists**, so NDCI is reported **relatively** - against clean-reference controls and each lake's own history - never as absolute mg/m^3.

### 5.2 Two tiers

- **Cached tier:** monthly NDCI time-series (2021-present) for six predefined polygons, producing per-lake mean/median/p75 and a `self_anomaly` flag (latest > own p75).
- **On-demand tier:** for arbitrary user GPS, a point buffer with **escalation** (150 -> 300 -> 500 m) to handle bank points and weed-choked shores; SCL-masked **median composite** over a 180-day window (monsoon-tolerant, since no single scene is <20% cloud for months in Bengaluru - verified: 0 clear scenes in a recent 60-day window); a **minimum water-pixel gate** (>=5) to reject sub-pixel / non-water points; comparison to a fixed clean-reference baseline (NDCI ~= 0.0155). A `spatial_confidence` qualifier (high/medium/low) records whether water was found at the tight buffer or only by widening the search.

### 5.3 Results (six-lake study)

Monthly-median NDCI:

| Water body | Category | Median NDCI |
|---|---|---|
| Hussain Sagar | polluted | 0.263 |
| Ulsoor | moderate | 0.346 |
| Bellandur | polluted | 0.189 |
| Varthur | polluted | 0.099 |
| Hesaraghatta | clean reference | 0.020 |
| Pangong | clean reference | -0.084 |

**Interpretation (C4).** Clean references anchor low (Pangong negative = clear oligotrophic water); all urban lakes sit above the ~0.0155 baseline - a separation the ground classifier could not achieve. **Caveat:** NDCI measures chlorophyll/algae specifically, so it does not reproduce the a-priori pollution ranking (Ulsoor, an intensely eutrophic small lake, reads highest). The result is framed as *"NDCI separates high-chlorophyll from clear water,"* not *"NDCI ranks general pollution."* On-demand values agree with the cached series (Bellandur ~= 0.24 via both paths). Note Hesaraghatta (a frequently low/dry reservoir) sits essentially *at* the baseline, not meaningfully above it.

### 5.4 Fusion policy

Ground and satellite signals are **not** probabilistically fused: blending a chance-level classifier (AUC 0.49) with a physical signal only adds noise. They are complementary - the report says *where/when* a citizen flags; the satellite provides *independent physical corroboration* for large bodies, surfaced as a categorical verdict (`elevated` / `watch` / `nominal` / `unavailable`).

---

## 6. System architecture

Flutter mobile app -> FastAPI (`/api/v1`) -> PostGIS proximity matching (nearest water body within 500 m, `ST_DWithin`) -> CV + classifier scoring -> **asynchronous** satellite enrichment (FastAPI `BackgroundTasks`; report saved and returned immediately with `status: processing_satellite`, satellite verdict polled via `GET /reports/{id}`) -> Leaflet dashboard + mobile result view. Rationale: on-demand GEE queries take 15-60 s and must not block report submission.

---

## 7. Limitations and threats to validity

1. **Small benchmark (N=200)** - CIs are wide; 5-fold CV is used to stabilise estimates.
2. **Label boundary** - "Low" images may still be visibly degraded urban water; the binary task is honestly *low vs high pollution*, not *pristine vs polluted*.
3. **Benchmark image licensing** - provenance for the scraped set is unrecorded; only the CC subset is redistributable.
4. **Satellite resolution** - 10-20 m; corroboration applies only to large water bodies. Drains, ponds, tanks, and thin rivers are sub-pixel and return "unavailable."
5. **No in-situ ground truth** - NDCI thresholds are relative, not absolute; satellite results are corroborative, not a calibrated chlorophyll product.
6. **Temporal mismatch** - scraped photos lack capture dates; satellite comparison is at water-body level, not per-photo.
7. **Approximate lake polygons** - must be tightened before publication (Ulsoor/Varthur most sensitive to shoreline-vegetation contamination).
8. **Clean-baseline definition** - the baseline is the mean of clean-reference p75s; a control lake (Hesaraghatta) sits marginally above it. Consider a Pangong-only baseline or a small margin so controls are not flagged as elevated.
9. **In-process background tasks** - a server restart mid-query drops enrichment; a task queue is needed for production.

---

## 8. Reproducibility

Frozen artifacts and scripts: pHash split + leakage audit; group-aware training; ablation harness (binary + 3-class); threshold-calibration (5-fold Youden, cached probabilities); low-vs-high inversion montage; Sentinel-2 time-series generator (project-parameterised); on-demand point service (service-account auth); manuscript-asset exporter. Fixed seeds where applicable; collection dates and per-image source URLs recorded for web-sourced data.

### 8.1 Scripts (under `backend/`)

| Script | Purpose |
|---|---|
| `phash_group_split.py` | de-leak EyeOnWater (group-aware split) |
| `train_efficientnet_group_aware.py` | train the classifier on the clean split |
| `scripts/audit_phash_leakage.py` | leakage audit (Hamming distances) |
| `scripts/ablation_harness.py` | ablation table (`--benchmark local`) |
| `scripts/calibrate_threshold.py` | 5-fold Youden threshold recalibration |
| `scripts/compare_low_high_prob.py` | OOD inversion montage |
| `scripts/validate_cv_detectors.py` | CV-detector vs pollution-type validation |
| `scripts/sentinel_ndci_timeseries.py` | Sentinel-2 monthly NDCI (GEE) |
| `scripts/export_manuscript_assets.py` | figures + Table 1 |
| `app/services/satellite.py` | cached + on-demand NDCI service |
| `datasets/IndianWaterDataset/collect_licensed_commons.py` | CC-licensed image collector |

### 8.2 Generated assets (under `backend/reports/`)

| File | Description |
|---|---|
| `figure1_ndci_timeseries.png` | Figure 1 - monthly NDCI per lake |
| `figure2_ood_vs_satellite.png` | Figure 2 - ground ROC (AUC 0.49) vs satellite NDCI |
| `paper_table_1_lake_summary.csv` | Table 1 - per-lake NDCI summary |
| `sentinel_ndci_monthly.csv` | full monthly NDCI series (414 rows) |
| `sentinel_lake_summary.csv` | per-lake NDCI aggregates |
| `low_high_prob_montage.png` | OOD inversion qualitative figure |
| `threshold_calibration.json` / `.txt` | calibration metrics + table |
| `ablation_results_local.json` / `ablation_table_local.txt` | ablation metrics + table |
| `benchmark_probs.csv` | cached per-image classifier probabilities |

**Absolute location on this machine:**
`c:\Users\Bhoomi Nayak\Downloads\aquawatch\backend\reports\`

## 9. Ethics and licensing

Model trained on citizen-science data (research use); publishable benchmark restricted to CC / public-domain imagery with attribution; no PII; satellite data under Copernicus open-data terms; results reported without overclaiming (relative anomaly, not calibrated measurement).
