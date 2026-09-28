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

Consequently:

- The images are **not redistributed** under any license in this repository
  (they are git-ignored).
- The benchmark is released **by reference only**, ImageNet-style: the
  `sha256` and `phash` in `docs/benchmark_provenance.csv` identify each image so
  that a recovered `source_url` can be added per row and users can re-fetch the
  originals under each source's own terms.
- Redistribution of any image requires first establishing its source and
  license and recording them in `benchmark_provenance.csv`. Until then, the
  `evidence_status` column reads `NO_EMBEDDED_EVIDENCE` and the images must be
  treated as all-rights-reserved third-party content.

## 4. Third-party training datasets

Training datasets (EyeOnWater, the river-segmentation set, the pollution-type
set) retain their original licenses and are not redistributed here. Trained
model weights derived from them are likewise not relicensed.

## 5. How to complete image provenance (author action)

For each row in `docs/benchmark_provenance.csv`, add the true `source_url`,
`license`, and `collection_date` from your collection records. Only images with
a verified free/redistributable license (e.g., CC0 / CC BY / CC BY-SA / public
domain) may be redistributed; all others remain reference-only.
