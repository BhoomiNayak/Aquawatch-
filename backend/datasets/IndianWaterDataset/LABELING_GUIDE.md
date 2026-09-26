# AquaWatch — Image Labeling Guide (For Annotators)

## Goal
We have **200 images** of Indian water bodies in `indian_test_set_200/`. Your job is to label each one as **Low / Moderate / High** pollution risk. This labeled set becomes the official benchmark that measures how accurate our AI model really is — it's the most important dataset in the whole project.

**3 people label all 200 images independently.** We then measure how much you agree (Fleiss' Kappa) and combine your answers into a final label.

---

## The 3 Labels

We use a **3-level scale**. Enter it as a number in the CSV:

| Value | Label | Meaning |
|-------|-------|---------|
| **0** | Low | Water looks clean/healthy |
| **1** | Moderate | Some visible pollution signs, not severe |
| **2** | High | Clearly, heavily polluted |

---

## Detailed Labeling Criteria

### 0 = LOW (Clean / Healthy)
Mark **Low** if the water shows:
- Clear, blue, or natural greenish water
- You can see through it or it looks fresh
- No foam, no trash, no scum
- Healthy lakes, restored ponds, flowing clean rivers
- Minor natural sediment is OK (a slightly muddy but otherwise clean river)

**Examples:** clean lake in a park, clear flowing stream, well-maintained tank.

### 1 = MODERATE (Some Pollution)
Mark **Moderate** if the water shows:
- Greenish tint from mild algae (not a full bloom)
- Slightly murky / cloudy water
- A little floating debris or leaves
- Some discoloration but not black/toxic-looking
- Early warning signs — "this needs monitoring"

**Examples:** a lake starting to green over, a pond with scattered litter, cloudy urban water.

### 2 = HIGH (Heavily Polluted)
Mark **High** if the water shows:
- White/brown **foam or froth** on the surface
- **Dark black, brown, or grey** water
- Thick **green algae bloom** covering the surface
- **Oil sheen** (rainbow film) or oil slicks (dark swirls)
- Visible **sewage, trash, plastic** floating
- Dead fish, heavy scum, toxic-looking water

**Examples:** Bellandur foam, Yamuna froth, algae-choked lake, garbage-filled nallah.

---

## How to Label (Step by Step)

1. Open the folder `indian_test_set_200/` and open `image_metadata.csv` in Excel or Google Sheets.
2. Look at each image (`image_001.jpg` … `image_200.jpg`) one at a time.
3. In the CSV, find the row for that image.
4. Fill in **only your own column**:
   - Annotator 1 → fill `annotator_1`
   - Annotator 2 → fill `annotator_2`
   - Annotator 3 → fill `annotator_3`
5. Enter **0, 1, or 2** based on the criteria above.
6. If an image is unclear, add a short note in the `notes` column (e.g., "mostly sky, hard to tell").

**CSV columns you'll see:**
```
image_id, filename, source_category, annotation_low_moderate_high, annotator_1, annotator_2, annotator_3, notes
```
- Leave `annotation_low_moderate_high` **blank** — that gets computed later from your 3 answers.
- Only fill your assigned `annotator_X` column.

---

## Critical Rules (Read This)

1. **Label independently.** Do NOT look at each other's answers or discuss individual images while labeling. The whole point is to measure genuine agreement. Talking defeats it.
2. **Judge only what you can SEE in the image.** Ignore the `source_category` (which lake it's from). A clean-looking photo of Bellandur is still "Low" even though Bellandur is famously polluted — we label the *image*, not the reputation.
3. **When genuinely torn between two levels, pick the higher one.** (Between Low and Moderate → Moderate. Between Moderate and High → High.) This is a safety-first triage system.
4. **Bad images:** if an image is NOT water (all sky, a map, a graph, a person, a screenshot), or is too blurry to judge — write "EXCLUDE" in the notes column and leave your label blank. We'll remove these.
5. **Be consistent.** Try to apply the same standard to image 1 and image 200. If you take a break, re-read the criteria when you come back.

---

## What NOT to Do

- Don't label based on the filename or lake name — only the visible water.
- Don't discuss specific images with other annotators during labeling.
- Don't skip images (except genuine EXCLUDE cases — note those).
- Don't overthink. First honest impression based on the criteria is usually right. Aim ~5-10 seconds per image.

---

## After Everyone Finishes

1. All 3 annotators send back their filled CSV (or fill a shared sheet in separate columns).
2. We run `fleiss_kappa.py` to measure agreement:
   - **Kappa > 0.6** = good agreement (publishable)
   - **Kappa 0.4-0.6** = moderate, we discuss disagreements
   - **Kappa < 0.4** = we need to re-align on criteria and re-label
3. Final label per image = **majority vote** of the 3 annotators (e.g., if two say High and one says Moderate → High).
4. Disagreements (all 3 different) get reviewed together.

---

## Time Estimate
~200 images × ~8 seconds each ≈ **25-30 minutes** of focused work per person. Do it in one or two sittings so your standard stays consistent.

---

## Quick Reference Card (keep this open while labeling)

```
┌──────────────────────────────────────────────────────┐
│  0 = LOW       clear / blue / clean, no issues         │
│  1 = MODERATE  mild algae, cloudy, some litter         │
│  2 = HIGH      foam / black water / bloom / oil / trash │
│                                                        │
│  Torn? → pick the HIGHER number                        │
│  Not water / unreadable? → note "EXCLUDE", leave blank │
│  Label what you SEE, not the lake's name               │
└──────────────────────────────────────────────────────┘
```

Thank you — this labeled set is what makes the whole project scientifically credible.
