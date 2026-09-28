# AquaWatch Benchmark — Data & Artifact Licensing

This document states, honestly and by component, what is licensed and what is
not. It deliberately does **not** assign a license to images the authors do not
own.

## 1. Author-owned artifacts — CC BY 4.0

The following are original work of the AquaWatch authors and are released under
the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license
(https://creativecommons.org/licenses/by/4.0/):

- The **annotations / severity labels** and consensus in
  `backend/datasets/local_benchmark/indian_validation_set.csv`.
- The **provenance metadata** in `docs/benchmark_provenance.csv`
  (image hashes, EXIF-extraction results, water-body names, cities).
- The **documentation** in `docs/` (methodology, paper drafts) and the
  **derived figures** in `docs/figures/` (plots computed by the authors).
- The `target_lakes.geojson` polygons.

Attribution: "AquaWatch (Pallavi K R, Bhoomi Prashanth Nayak, Hrithika
Vishwanath Shetty, Sonika G K, Varsha H L), SJMVIT, 2026."

## 2. Source code — MIT

All source code is under the MIT License (see the repository root `LICENSE`).

## 3. The 200 benchmark images — NOT licensed here (UNRESOLVED)

The 200 images in `backend/datasets/local_benchmark/images/` were collected from
the web. An automated scan (`backend/scripts/extract_image_provenance.py`) found
**no embedded author/copyright/rights metadata in any of the 200 files** (EXIF
stripped). The authors therefore **do not hold and cannot grant** a license to
these images, and their per-image provenance is **UNRESOLVED**.

Consequently, by the authors' decision:

- The images are **not released or redistributed in any form** — not as files
  and not by URL reference. They are git-ignored and used **solely for internal
  evaluation** to produce the aggregate metrics reported in the paper.
- What *is* shared is the authors' own work: the labels/annotations, the
  provenance metadata (hashes), the code, the docs, and the derived figures
  (Sections 1–2 above).
- The `sha256`/`phash` in `docs/benchmark_provenance.csv` are retained for the
  authors' internal integrity and de-duplication checks only.
- Because the images are not released, external reproducibility is limited to
  the reported metrics and the labelling protocol (stated as a limitation in
  the paper).

## 4. Third-party training datasets

Training datasets (EyeOnWater, the river-segmentation set, the pollution-type
set) retain their original licenses and are not redistributed here. Trained
model weights derived from them are likewise not relicensed.

## 5. How to complete image provenance (author action)

For each row in `docs/benchmark_provenance.csv`, add the true `source_url`,
`license`, and `collection_date` from your collection records. Only images with
a verified free/redistributable license (e.g., CC0 / CC BY / CC BY-SA / public
domain) may be redistributed; all others remain reference-only.
