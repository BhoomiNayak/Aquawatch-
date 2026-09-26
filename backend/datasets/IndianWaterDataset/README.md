# Indian Water Dataset — Teammate 1

## Purpose
This package automates collection and cleanup of candidate images of polluted Indian urban water bodies.

## Setup
Open a terminal in this folder and run:

```bash
pip install -r requirements.txt
```

## Run

### 1. Scrape candidate images
```bash
python scrape_indian_water.py
```

This creates:
`dataset_indian_raw/`

### 2. Remove exact duplicate/corrupt images
```bash
python clean_dataset.py
```

### 3. Create a 200-image candidate test set
```bash
python make_test_set.py
```

This creates:
- `indian_test_set_200/`
- `image_metadata.csv`

## VERY IMPORTANT — human curation
The scraper does not guarantee:
- that every image is genuinely from India,
- that every image is geotagged,
- that every image is relevant,
- or that every image has permission for your intended use.

Therefore, manually inspect the 200 candidates. Remove irrelevant, duplicate-looking, screenshot, map, graphic, or unrelated images. Record source/licensing information if your project requires it.

Do not describe these Google Image results as "geotagged" unless you have separately verified geolocation metadata or a reliable source location.

## Annotation
Three annotators can fill `image_metadata.csv`:
- 0 = Low
- 1 = Moderate
- 2 = High

Columns:
`annotator_1`, `annotator_2`, `annotator_3`

After annotation, install statsmodels if needed and run:

```bash
python fleiss_kappa.py
```

## License-aware collection (use this for the PUBLISHED benchmark)

`scrape_indian_water.py` uses Google Image crawling, which captures **no license
or attribution data**. Those images have unknown, presumptively copyrighted
provenance — fine for a private accuracy experiment, but they **cannot be
redistributed** in a published dataset, and a reviewer asking "what license is
your data?" would reject it.

For anything that ships with the paper, collect from Wikimedia Commons instead:

```bash
pip install requests
python collect_licensed_commons.py --per-query 40
```

This creates:
- `commons_licensed/<category>/` — images under a free license only
  (CC0 / public-domain / CC-BY / CC-BY-SA)
- `commons_metadata.csv` — per-image provenance: license short-name, license
  code, author, source page URL, and collection date

The metadata CSV carries the same `annotation_low_moderate_high` /
`annotator_1/2/3` columns, so the labeling + `fleiss_kappa.py` workflow is
unchanged. Human curation is still required (remove non-water / non-India /
duplicate images) before labeling.

Notes:
- The collector downloads bounded-width thumbnails (Wikimedia's recommended
  path) and backs off on HTTP 429 rate limits.
- Keep `commons_metadata.csv` with the dataset — it is your attribution record.

## Suggested final deliverables
- `indian_test_set_200.zip`
- `image_metadata.csv`
- `scrape_indian_water.py`
- `clean_dataset.py`
- `make_test_set.py`
- `fleiss_kappa.py`

## Reproducibility note
Web image search results can change over time. Keep the scripts, query list, date of collection, and metadata/source information with the project.
