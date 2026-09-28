# [TITLE — AUTHOR DECISION REQUIRED] AquaWatch: A Cross-Modal Citizen-Science System for Water-Pollution Triage with Out-of-Distribution Validation and Sentinel-2 Corroboration

> **Title discrepancy (author approval required — not resolved here).** Three titles exist across sources:
> (a) original manuscript — "AquaWatch: Computer Vision and Machine Learning-Based Water Pollution Risk Assessment";
> (b) audit brief — "AquaWatch: A Citizen-Centric Platform for Urban Water Quality Monitoring";
> (c) v2/v3 revision — "AquaWatch: A Cross-Modal Citizen-Science System … Sentinel-2 Corroboration".
> Authors must select one. The line above is a working placeholder, not a decision.

**Pallavi K R¹, Bhoomi Prashanth Nayak², Hrithika Vishwanath Shetty³, Sonika G K⁴, Varsha H L⁵**
Department of Computer Science and Engineering, Sir M Visvesvaraya Institute of Technology, Bengaluru, India

Emails: ¹ **[AUTHOR EMAIL REQUIRED — original manuscript contained a placeholder]**; ² nayakbhoomi1704@gmail.com; ³ hrithikashetty839@gmail.com; ⁴ sonikagk8@gmail.com; ⁵ varshahl060@gmail.com

---

> **Revision note (v4, assembled).** This version merges the original manuscript's front matter, Figures 1–5, and bibliography [1]–[23] with the audit-corrected v3 technical content (`PAPER_v3_revised.md`), and adds: limited scientific wording for the six-water-body NDCI comparison; "prototype" in place of "deployable"; numbered display equations (1)–(3); numbered table captions (Table I–II). Originals (`PAPER_v2.md`, `PAPER_v3_revised.md`, `AquaWatch_Paper_v2.docx`) are preserved unchanged. Unresolved items (benchmark provenance; deployed-vs-evaluated model) remain flagged.

## Abstract

Urban lakes, ponds, and streams in rapidly developing cities such as Bengaluru, India, are increasingly affected by pollution and inadequate monitoring. The large number of water bodies makes frequent manual inspection difficult, motivating affordable and scalable methods. This paper presents AquaWatch, a citizen-centric platform in which users submit GPS-tagged photographs of water bodies through a mobile application and receive an automated pollution-risk estimate. The ground pipeline combines a seven-factor computer-vision (CV) analysis (Forel–Ule colour, algae, foam, turbidity, oil sheen, colour abnormality, and floating debris) with two learned models — an EfficientNet-B0 binary classifier and a YOLOv8n-seg model — fused into a 0–100 risk score classified as Low, Moderate, or High. Rather than reporting only in-distribution accuracy, we construct a human-annotated Indian water benchmark (N = 200; three annotators; Fleiss κ = 0.76 severity, 0.80 binary) and evaluate every component on it. We find a severe out-of-distribution (OOD) failure: a classifier that attains 99.9 % on a leakage-controlled in-distribution *validation* set (best-epoch-selected on that same split; no separate untouched in-distribution test set was held out) collapses to chance discrimination (ROC-AUC ≈ 0.49) on real Indian imagery, and post-hoc threshold recalibration (five-fold cross-validated Youden's J) does not repair it. Motivated by this, we add an independent Sentinel-2 corroboration layer (via Google Earth Engine) that computes the Normalized Difference Chlorophyll Index (NDCI) over water-masked pixels; in a six-water-body comparison, NDCI separates eutrophic urban lakes from clean-reference controls where the image classifier does not. Each report is linked to a nearby water body via PostgreSQL/PostGIS (500 m) and the satellite verdict is produced asynchronously. We present the system design, benchmark, experimental protocol, honest results, and limitations, and argue that the appropriate role of ground imagery is triage while satellite indices provide physical corroboration.

**Keywords—** citizen science, water pollution monitoring, computer vision, out-of-distribution generalization, EfficientNet, Sentinel-2, NDCI, Forel–Ule colourimetry, geospatial analysis, mobile crowdsourcing.

---

## I. Introduction

Remote sensing is widely used to observe water quality across large areas; reviews of satellite methods report useful estimation of chlorophyll-a, turbidity, and coloured dissolved organic matter, while noting practical issues such as cloud interference, mixed pixels, calibration, and difficulty monitoring small water bodies [1]. Optical and sensor systems can support automated monitoring but emphasize measurement uncertainty [2] and depend on installed hardware [15]. Pressure–impact frameworks assess surface-water contamination risk from monitoring data rather than direct visual observation [3]. Aerial AI approaches detect floating waste from drone imagery but are not evaluated on ground-level citizen photographs [8]. Integrations of remote sensing, IoT, and GIS improve coverage [13] yet rarely incorporate citizen-submitted images or CV-based risk assessment.

A distinct and under-examined risk in image-based citizen monitoring is generalization: a model trained on one image distribution may perform well in validation yet fail on field imagery from a different region. Prior citizen/vision systems seldom quantify this gap on an independent, locally labelled benchmark. This paper treats that gap as a first-class research question.

The main contributions of this work are:

- A citizen mobile application for submitting GPS-tagged water-body images and an operational FastAPI/PostGIS backend that links each report to a nearby water body.
- A seven-factor CV pipeline combined with two learned models (EfficientNet-B0 classifier; YOLOv8n-seg) producing a calibrated 0–100 risk score (Low/Moderate/High).
- A curated Indian water benchmark (N = 200) with three independent annotators and substantial inter-rater agreement (Fleiss κ = 0.76/0.80), used strictly for evaluation.
- An honest out-of-distribution analysis showing that a 99.9 %-in-distribution (validation) classifier collapses to ROC-AUC ≈ 0.49 on Indian water, that an ensemble merely matches the base rate, and that threshold recalibration is insufficient — a cautionary, reproducible negative result.
- A Sentinel-2 corroboration layer (Google Earth Engine) computing NDCI over NDWI-masked water pixels, delivered as an asynchronous per-report verdict, which separates eutrophic from clear water in a six-water-body comparison where the image model does not.

The remainder of the paper is organized as follows. Section II reviews related work. Section III describes the methodology and system architecture. Section IV presents the benchmark, experimental protocol, and results. Section V discusses limitations and future work. Section VI concludes.

---

## II. Literature Review

### A. Laboratory and chemical monitoring
Traditional monitoring relies on laboratory/field measurement of BOD, dissolved oxygen, pH, nitrates, and coliforms to compute Water Quality Index values [16], and on chemical assays of hydrocarbons, heavy metals, and pharmaceuticals [9], [19], [20], including polycyclic aromatic hydrocarbons [4], microplastics in water and drinking-water sources [6], and heavy-metal contamination in mining-affected basins [10]. These give detailed, authoritative measurements but require sampling and lab facilities, limiting continuous large-scale coverage.

### B. Sensor and IoT-based monitoring
IoT and automated systems continuously measure pH, turbidity, dissolved oxygen, agricultural nutrient runoff [5], and cyanobacterial blooms [15], [21], [23], but coverage is limited to instrumented sites [12], [18]. Low-cost IoT/drone/remote-sensing technologies have been explored for developing regions, yet real-time analysis of citizen ground-level images remains under-addressed [22].

### C. Remote sensing and GIS
Satellite/GIS approaches monitor surface water over large regions [7], [11], [14], and AI has been applied to remote-sensing data for water-body detection and quality estimation [14]. Spectral indices such as NDWI for water delineation [27] and NDCI for chlorophyll [26] are well established, but depend on resolution and, for absolute quantities, in-situ calibration [1], [19].

### D. AI and data-driven monitoring
Machine learning is increasingly applied to environmental sensing and remote-sensing data [14], [18], [22], and systems approaches integrate pollution sources, models, and spatial information for management [17]. However, most systems use sensor or satellite inputs rather than citizen ground-level imagery, and — importantly — rarely report generalization to an independent, locally labelled test set.

### E. Research gap
Existing work spans lab/chemical [9], [16], [19], [20], sensor/IoT [15], [21], [23], remote sensing/GIS [7], [11], [14], and AI-based analysis [14], [18], [22]. Two gaps remain: (i) integrating citizen ground-level photographs, CV/ML risk estimation, geospatial association, and web visualization in one platform; and (ii) honestly quantifying whether image-based classifiers generalize to local field imagery, and what to do when they do not. AquaWatch addresses both — the first with an end-to-end system, the second with a locally annotated benchmark and a cross-modal satellite corroboration layer.

---

## III. Methodology

### A. System design and architecture
Users capture a water-body image in the Flutter app and provide GPS location, contamination type, and optional notes; the request is sent to a FastAPI backend (`/api/v1`). The image is analysed by the seven-factor CV pipeline and by two learned models, fused into a risk score. The report is stored in PostgreSQL and linked by PostGIS to the nearest known water body within 500 m. A satellite corroboration verdict is then computed asynchronously and attached to the report. Results are served to a Leaflet dashboard and the mobile result view. The overall architecture is shown in Fig. 1.

> **[FIGURE 1 — insert from original manuscript]** System architecture of the AquaWatch platform, showing the mobile application, image-analysis pipeline, machine-learning layer, risk scoring, geospatial database, and web dashboard. *(Image file to be supplied by authors from the original manuscript.)*

### B. Mobile data collection and GPS
The Flutter application guides users to capture a suitable image (fill frame with water, avoid glare), records GPS coordinates, and submits image plus metadata with retry handling. GPS enables spatial association and mapping.

### C. Seven-factor computer-vision pipeline
Using OpenCV, each image yields seven indicators: Forel–Ule colour (21-point limnological scale), algae (green-hue fraction in HSV), foam (bright low-saturation blob/contour analysis), turbidity (Laplacian variance with a dark-water penalty), oil sheen (rainbow iridescence via local hue variance plus thick-slick detection), colour abnormality (statistical distance from natural water colours), and surface debris (contour density). All seven are heuristic appearance indicators, not validated water-quality measurements. They are combined with fixed weights (turbidity 0.18, foam 0.18, debris 0.17, algae 0.15, colour abnormality 0.15, Forel–Ule 0.10, oil 0.07) into a composite score S ∈ [0, 100], classified Low (0–15), Moderate (16–35), High (36–100).

### D. Learned models and fusion
EfficientNet-B0 [24] (ImageNet-initialised, two-class head) is fine-tuned on the EyeOnWater citizen dataset (22,376 images; 12,357 clean / 10,019 polluted). To prevent near-duplicate leakage, images are clustered by perceptual hash and split group-aware (20,907 clusters; minimum cross-split Hamming distance 12; no leakage), yielding a leakage-controlled **validation** accuracy of 0.9989 (99.89 %). This is a best-epoch figure selected on that same validation split; **no separate, untouched in-distribution test set was held out**, so it must be read as validation—not test—performance. YOLOv8n-seg [25] is trained on a river-water segmentation set (949 images; clean/turbid/polluted; in-domain mAP@0.5 = 0.836). Although a segmentation model, **only its highest-confidence detection (class and confidence) is used for the image-level label; segmentation masks are not used in the risk calculation.** At inference, EfficientNet acts as the primary authority and YOLO provides a bounded boost only when the classifier agrees; a CV safety net forces High risk on strong visual indicators (e.g., foam or debris coverage > 30 %).

### E. Geospatial processing
PostgreSQL stores water bodies, reports, and historical risk snapshots; PostGIS performs proximity matching with `ST_DWithin` on geography-cast POINT geometries (SRID 4326). A new report is associated with the nearest water body within 500 m, or a new record is created, so nearby observations accumulate into one monitoring history.

### F. Sentinel-2 corroboration layer
Sentinel-2 L2A imagery (`COPERNICUS/S2_SR_HARMONIZED`) is accessed through Google Earth Engine [28]. Cloud/shadow pixels are removed via the Scene Classification Layer. Water pixels are delineated with the McFeeters NDWI [27] (Eq. 1), keeping NDWI > 0, and chlorophyll is estimated with the NDCI [26] (Eq. 2), averaged over water-masked pixels at 20 m.

NDWI = (B3 − B8) / (B3 + B8)     (1)

NDCI = (B5 − B4) / (B5 + B4)     (2)

where B3, B4, B5, and B8 are the Sentinel-2 green, red, red-edge, and near-infrared surface-reflectance bands, respectively.

Two tiers are provided. A cached tier precomputes monthly NDCI series (2021–present) for tracked lakes, yielding per-lake median/75th-percentile statistics. An on-demand tier handles arbitrary user GPS: it buffers the point (escalating 150 → 300 → 500 m to reach open water on weed-choked shorelines), builds an SCL-masked median composite over a 180-day window (monsoon-tolerant, since single <20 %-cloud scenes are unavailable for months in Bengaluru), enforces a minimum water-pixel gate to reject sub-pixel targets, and compares NDCI to a fixed clean-reference baseline. Because no in-situ chlorophyll is available, scoring is relative (versus clean references and a lake's own history), never absolute. The satellite verdict (elevated/watch/nominal/unavailable) is computed asynchronously (FastAPI `BackgroundTasks`) so it never blocks report submission; clients poll the report until the verdict resolves. The satellite signal is deliberately not probabilistically fused with the image classifier — blending a chance-level signal would only add noise — but is presented as independent physical corroboration.

### G. Dashboard
A Leaflet.js dashboard (HTML/CSS/JS, no build step) maps water bodies coloured by risk category, with per-water-body detail (score, factor breakdown, recent reports, and satellite badge) and periodic refresh. The methodology pipeline is summarised in Fig. 2.

> **[FIGURE 2 — insert from original manuscript]** Overview of the methodology (image collection, preprocessing, seven-factor feature extraction, risk scoring, optional ML classification, geospatial matching, storage, and dashboard). *(Image file to be supplied by authors from the original manuscript.)*

---

## IV. Results and Implementation

The platform is implemented with a Flutter app, a FastAPI backend, OpenCV/PyTorch analysis, PostgreSQL/PostGIS storage, GEE-based satellite analysis, and a Leaflet dashboard. Beyond functional testing of the reporting workflow, we conduct a quantitative evaluation on an independent benchmark.

### A. Indian water benchmark
We assembled 200 real Indian water-body images spanning lakes, rivers, drains, and reservoirs across multiple cities. Three annotators independently labelled each image on a three-level severity scale (0 = Low, 1 = Moderate, 2 = High); the consensus is the per-image majority (all resolvable). Distribution: 71 Low, 75 Moderate, 54 High. Inter-rater agreement is substantial: Fleiss κ = 0.757 (three-class) and 0.795 (binary Low vs Moderate+High) [29]. The benchmark is used only for evaluation; no model is trained on it. Labels reflect **visible/apparent** pollution severity, not laboratory-verified water quality. **Per-image source URLs and licenses are not yet recorded in the released metadata `[PROVENANCE TO VERIFY]`**; the required evidence and its implications for redistribution are stated in Section V.

### B. Component ablation
Table I reports the binary (clean vs polluted) ablation on the benchmark; the polluted base rate is 64.5 %.

**TABLE I.** Component ablation on the Indian benchmark (binary framing: clean vs polluted).

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| CV-only | 56.5 % | 61.7 % | 86.1 % | 71.8 % |
| EfficientNet-only | 61.0 % | 63.5 % | 93.0 % | 75.5 % |
| YOLO-only | 43.8 % | 68.0 % | 30.1 % | 41.7 % |
| Ensemble | 64.5 % | 64.6 % | 99.2 % | 78.3 % |

Three-class (Low/Moderate/High): CV-only 32.0 % (macro-F1 22.8 %); Ensemble 27.0 % (macro-F1 18.6 %) — at or below the 37.5 % majority-class baseline. The ensemble's 64.5 % accuracy equals the base rate, with precision ≈ base rate and recall 99.2 %: it predicts "polluted" almost always rather than discriminating.

### C. Out-of-distribution failure and threshold recalibration
The classifier's threshold-independent ROC-AUC on the benchmark is 0.49 (chance). The association between predicted pollution probability and human severity is essentially null: **Spearman ρ = −0.012** (rank-based, appropriate for the ordinal severity labels and robust to the many probabilities saturated at 1.0), with **Pearson r = −0.116**; neither indicates a usable monotonic relationship. Under the default threshold τ = 0.5, sensitivity is 93.0 % but specificity only 2.8 %. Recalibrating with Youden's J [30] (Eq. 3), selected **per-fold on training folds and evaluated out-of-fold under five-fold stratified cross-validation**, raises specificity to 32.4 % but reduces accuracy to 55.0 % ± 3.5 % and F1 to 65.8 % — trading errors along a diagonal ROC. We therefore report a **five-fold cross-validated estimate on the 200-image benchmark, not held-out test performance**.

J(τ) = sensitivity(τ) + specificity(τ) − 1 ;   τ* = argmax_τ J(τ)     (3)

The in-distribution-to-benchmark accuracy gap is 99.9 % (validation) → 55.0 % (≈ 45 pp). Qualitatively (Fig. 8), the images the model is most confident are clean are predominantly labelled High by humans, and vice-versa. We conclude that the failure is representational, not a calibration artifact; post-hoc thresholding cannot repair a model lacking discriminative signal on this domain.

![Fig. 6](figures/figure2_ood_vs_satellite.png)

**Fig. 6.** Cross-modal contrast. (A) The ground classifier's ROC curve on the Indian benchmark hugs the chance diagonal (AUC ≈ 0.49); (B) Sentinel-2 NDCI separates eutrophic urban lakes from clean-reference controls relative to the clean baseline in the six-water-body comparison.

### D. Sentinel-2 corroboration
Table II reports monthly-median NDCI over the six study water bodies.

**TABLE II.** Sentinel-2 monthly-median NDCI per water body (2021–present).

| Water body | Category | Median NDCI |
|---|---|---|
| Hussain Sagar | polluted | 0.263 |
| Ulsoor | moderate | 0.346 |
| Bellandur | polluted | 0.189 |
| Varthur | polluted | 0.099 |
| Hesaraghatta | clean reference | 0.020 |
| Pangong | clean reference | −0.084 |

Clean references anchor low (Pangong negative, indicating clear oligotrophic water), and every urban lake sits above the ≈ 0.0155 clean-reference baseline. In this six-water-body comparison, NDCI separates high-chlorophyll from clear water — the discrimination the ground classifier could not achieve (Fig. 7). We note NDCI measures chlorophyll/eutrophication specifically (hence the intensely eutrophic small lake Ulsoor reads highest), so it is reported as a chlorophyll axis, not a general pollution rank; the frequently low/dry Hesaraghatta reservoir sits essentially at the baseline. These are relative comparisons over six water bodies without in-situ calibration and should not be read as validated chlorophyll concentrations.

![Fig. 7](figures/figure1_ndci_timeseries.png)

**Fig. 7.** Sentinel-2 monthly NDCI time-series (2021–present) per water body, with the clean-reference baseline. Polluted urban lakes remain elevated relative to the clean controls across seasons.

![Fig. 8](figures/low_high_prob_montage.png)

**Fig. 8.** Qualitative out-of-distribution inversion. The ten images the classifier is most confident are "clean" (top) versus most confident are "polluted" (bottom), captioned with the human consensus label; the model's confidence is anti-correlated with the ground truth.

### E. Functional system
The mobile app produces per-report results (composite score, level, factor breakdown, AI classification) and displays the asynchronously populated satellite verdict; the dashboard maps water bodies by risk with detail panels and satellite badges (Figs. 3–5). As a **traceable worked example** — replacing an earlier illustrative "40.5/100" figure whose original input image and API response were not logged and could not be recovered (**disclosed replacement**) — the seven-factor CV composite for the committed benchmark image `IND_003.jpg` evaluates to **10.0/100 (Low)**: algae 0.69 + foam 0.05 + turbidity 5.65 + Forel–Ule 0.00 + oil 0.18 + colour-abnormality 1.65 + debris 1.82 = 10.04. This image carries a human consensus label of **High**, illustrating both the arithmetic of the weighted composite and the limited reliability of appearance-based scoring analysed in Section IV.C. (The figure is the model-independent CV composite; optional EfficientNet/YOLO boosts apply only in the deployed ensemble path.)

> **[FIGURE 3 — insert from original manuscript]** AquaWatch mobile application: home screen and report-submission interface (captured image, GPS location, contamination type, optional notes). *(Image file to be supplied by authors.)*

> **[FIGURE 4 — insert from original manuscript]** AquaWatch analysis-result screen showing risk classification, composite score, AI classification, and CV factor breakdown. *(Image file to be supplied by authors.)*

> **[FIGURE 5 — insert from original manuscript]** AquaWatch web dashboard: spatial distribution of water bodies, risk levels, analysis details, and recent reports. *(Image file to be supplied by authors.)*

---

## V. Limitations and Future Work

1. Small benchmark (N = 200). Confidence intervals are wide; we mitigate with cross-validation and report variance.
2. Label boundary. "Low" images are often visibly degraded urban water, so the binary task is honestly low-vs-high pollution rather than pristine-vs-polluted.
3. Image licensing / provenance (**UNRESOLVED**). The 200-image benchmark's per-image source URLs, licenses, and collection dates are not yet recorded in the released metadata; only a CC-licensed subset is redistributable. Required evidence before publication: per-image source URL, license, and collection date. The benchmark must not be redistributed until this is complete.
4. Satellite resolution. At 10–20 m, corroboration applies only to sufficiently large water bodies; drains, ponds, and thin rivers are sub-pixel and return "unavailable."
5. No in-situ ground truth. NDCI is relative, not an absolute chlorophyll measurement; results are corroborative and limited to a six-water-body comparison.
6. Domain gap. The primary future direction is in-domain training data (including genuinely clean Indian water) rather than post-hoc tuning; the classifier should be re-evaluated after fine-tuning.
7. Operational. On-demand satellite queries run as in-process background tasks; a production deployment should use a task queue, and lake polygons should be tightened before publication.
8. Deployed-vs-evaluated model (**UNRESOLVED**). All reported classifier/ensemble metrics use the group-aware EfficientNet checkpoint (`split=group_aware_phash`, val acc 0.9989). The currently deployed API loads a *different* checkpoint trained on a random split (val acc 0.9975), which is not the evaluated model and whose validation figure is not leakage-controlled. Any claim that the deployed system attains the reported ablation/OOD numbers depends on reconciling this discrepancy; until then, deployed accuracy is not established.

---

## VI. Conclusion

AquaWatch is a **prototype** citizen-science platform that combines mobile image collection, a seven-factor CV pipeline, learned classifiers, geospatial association, and web visualization, together with an independent Sentinel-2 corroboration layer. Its principal scientific contribution is honesty: on a locally annotated benchmark, an image classifier with 99.9 % in-distribution *validation* accuracy is shown to collapse to chance (ROC-AUC ≈ 0.49) out-of-distribution, and threshold recalibration cannot recover it — while, in a six-water-body comparison, satellite NDCI separates eutrophic from clear water. The appropriate role for ground imagery is therefore preliminary triage, with satellite indices providing physical corroboration for large water bodies. Future work will pursue in-domain training data, in-situ validation, and broadened spatial coverage.

---

## References

[1] S. Ngamile, S. Madonsela, and M. Kganyago, "Trends in remote sensing of water quality parameters in inland water bodies: A systematic review," *Frontiers in Environmental Science*, vol. 13, Art. no. 1549301, 2025, doi: 10.3389/fenvs.2025.1549301.

[2] S. Penzel, T. Mayer, H. Borsdorf, M. Rudolph, and O. Kanoun, "In situ water quality monitoring for the assessment of algae and harmful substances in water bodies with consideration of uncertainties," *Sensors*, vol. 25, no. 22, Art. no. 7055, 2025, doi: 10.3390/s25227055.

[3] S. Aydi, J. Paredes-Arquiola, R. J. Bergillos, A. Solera, and J. Andreu, "A pressure-impact approach to assess contamination and risk in surface water bodies," *Hydrology*, vol. 12, no. 11, Art. no. 301, 2025, doi: 10.3390/hydrology12110301.

[4] Q. Chen, T. Song, J. Kong, J. Zhang, L. Zhu, et al., "Occurrence, composition, sources, and ecological-health risk assessment of polycyclic aromatic hydrocarbons in Chinese water bodies: A review," 2025.

[5] M. Awais, Y. Chen, W. Zhang, S. M. Z. A. Naqvi, H. Zhang, V. Raghavan, J. Hu, and I. Tlili, "Experimental validation of an automated soil leachate monitoring system for agricultural non-point source pollution and nutrient run-off to water bodies," *Ain Shams Engineering Journal*, vol. 16, no. 11, Art. no. 103713, 2025, doi: 10.1016/j.asej.2025.103713.

[6] A. Bhowmik and G. Saha, "Microplastics in our waters: Insights from a configurative systematic review of water bodies and drinking water sources," *Microplastics*, vol. 4, no. 2, Art. no. 24, 2025, doi: 10.3390/microplastics4020024.

[7] U. Mukhtorov, B. Kakhorov, Z. Khafizova, D. Murodova, and R. Egamberdiev, "Study of monitoring of water bodies using remote sensing data and GIS technologies (Talimarjan water reservoir)," *IOP Conf. Series: Earth and Environmental Science*, vol. 1420, no. 1, Art. no. 012007, 2024, doi: 10.1088/1755-1315/1420/1/012007.

[8] A. D. Bypilla, J. V. D. Prasad, B. Kota, et al., "A YOLO-based aerial monitoring system for detecting waste in water bodies," 2024.

[9] P. K. Singh, U. Kumar, I. Kumar, A. Dwivedi, P. Singh, S. Mishra, C. S. Seth, and R. K. Sharma, "Critical review on toxic contaminants in surface water ecosystem: Sources, monitoring, and its impact on human health," *Environmental Science and Pollution Research*, vol. 31, pp. 56428–56462, 2024, doi: 10.1007/s11356-024-34932-0.

[10] V. Popovych, V. Skrobala, O. Tyndyk, and O. Kaspruk, "Hydro-ecological monitoring of heavy metal pollution of water bodies in the Western Bug River basin within the mining-industrial region," *Mining of Mineral Deposits*, vol. 18, no. 4, pp. 139–152, 2024, doi: 10.33271/mining18.04.139.

[11] N. T. Dolchinkov, "Construction of a system for monitoring the pollution of water bodies with waste," *Environment. Technology. Resources*, vol. 1, pp. 136–141, 2024, doi: 10.17770/etr2024vol1.7989.

[12] O. Afanaseva, M. Afanasyev, S. Neyrus, D. Pervukhin, and D. Tukeev, "Information and analytical system monitoring and assessment of the water bodies state in the mineral resources complex," *Inventions*, vol. 9, no. 6, Art. no. 115, 2024, doi: 10.3390/inventions9060115.

[13] Y. Sudriani, V. Sebestyén, and J. Abonyi, "Surface water monitoring systems—The importance of integrating information sources for sustainable watershed management," 2023.

[14] L. Yang, J. Driscol, S. Sarigai, Q. Wu, C. D. Lippitt, et al., "Towards synoptic water monitoring systems: A review of AI methods for automating water body detection and water quality monitoring using remote sensing," 2022.

[15] V. Lakshmikantha, A. Hiriyannagowda, et al., "IoT based smart water quality monitoring system," 2021.

[16] R. Nayar, "Assessment of water quality index and monitoring of pollutants by physico-chemical analysis in water bodies: A review," 2020.

[17] J. S. Shortle, J. R. Mihelcic, Q. Zhang, and M. Arabi, "Nutrient control in water bodies: A systems approach," *Journal of Environmental Quality*, vol. 49, no. 3, pp. 517–533, 2020, doi: 10.1002/jeq2.20022.

[18] S. L. Ullo and G. R. Sinha, "Advances in smart environment monitoring systems using IoT and sensors," *Sensors*, vol. 20, no. 11, Art. no. 3113, 2020, doi: 10.3390/s20113113.

[19] Z. Yigit Avdan, G. Kaplan, S. Goncu, and U. Avdan, "Monitoring the water quality of small water bodies using high-resolution remote sensing data," *ISPRS Int. J. Geo-Information*, vol. 8, no. 12, Art. no. 553, 2019, doi: 10.3390/ijgi8120553.

[20] Y. Hu, A. M. Sampat, G. J. Ruiz-Mercado, et al., "Logistics network management of livestock waste for spatiotemporal control of nutrient pollution in water bodies," 2019.

[21] V. Tran Khac, Y. Hong, D. Plec, B. J. Lemaire, P. Dubois, M. Saad, and B. Vinçon-Leite, "An automatic monitoring system for high-frequency measuring and real-time management of cyanobacterial blooms in urban water bodies," *Processes*, vol. 6, no. 2, Art. no. 11, 2018, doi: 10.3390/pr6020011.

[22] M. V. Japitana, E. V. Palconit, A. T. Demetillo, M. E. C. Burce, E. B. Taboada, and M. L. S. Abundo, "Integrated technologies for low cost environmental monitoring in the water bodies of the Philippines: A review," *Nature Environment and Pollution Technology*, vol. 17, no. 4, pp. 1125–1137, 2018.

[23] G. S. Menon, M. V. Ramesh, and P. L. Divya, "A low cost wireless sensor network for water quality monitoring in natural water bodies," in *Proc. IEEE Global Humanitarian Technology Conference (GHTC)*, 2017, pp. 1–8, doi: 10.1109/GHTC.2017.8239341.

[24] M. Tan and Q. V. Le, "EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks," in *Proc. ICML*, 2019. arXiv:1905.11946.

[25] G. Jocher, A. Chaurasia, and J. Qiu, "Ultralytics YOLOv8," 2023. [Online]. Available: https://github.com/ultralytics/ultralytics

[26] S. Mishra and D. R. Mishra, "Normalized difference chlorophyll index: A novel model for remote estimation of chlorophyll-a concentration in turbid productive waters," *Remote Sensing of Environment*, vol. 117, pp. 394–406, 2012, doi: 10.1016/j.rse.2011.10.016.

[27] S. K. McFeeters, "The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features," *Int. J. Remote Sensing*, vol. 17, no. 7, pp. 1425–1432, 1996, doi: 10.1080/01431169608948714.

[28] N. Gorelick, M. Hancher, M. Dixon, S. Ilyushchenko, D. Thau, and R. Moore, "Google Earth Engine: Planetary-scale geospatial analysis for everyone," *Remote Sensing of Environment*, vol. 202, pp. 18–27, 2017, doi: 10.1016/j.rse.2017.06.031.

[29] J. L. Fleiss, "Measuring nominal scale agreement among many raters," *Psychological Bulletin*, vol. 76, no. 5, pp. 378–382, 1971, doi: 10.1037/h0031619.

[30] W. J. Youden, "Index for rating diagnostic tests," *Cancer*, vol. 3, no. 1, pp. 32–35, 1950.

*Note: DOIs/venues for [1]–[23] are carried over from the original manuscript and for [24]–[30] are canonical; verify all against the final reference manager. Original in-text citation numbering was internally inconsistent (see the citation reconciliation report); numbering here follows the bibliography above.*
