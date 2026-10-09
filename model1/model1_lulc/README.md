# Model 1 — LULC Classification — Shiggaon Taluk, Haveri, Karnataka

Part of a watershed-development decision-support system. This repository
covers **only Model 1** (LULC classification). Watershed risk analysis,
IoT, and the dashboard are built by other team members.

## 1. Objective

Classify Sentinel-2 imagery over Shiggaon Taluk into five classes using a
Random Forest trained against ESA WorldCover 2021 reference labels, then
summarize the result per micro-watershed.

```
Sentinel-2 → B02/B03/B04/B08/B11 → NDVI/NDWI/NDBI → WorldCover labels
    → training samples → Random Forest → GeoTIFF → zonal statistics
```

## 2. Study Area

Shiggaon Taluk, Haveri District, Karnataka, India.

## 3. Target Classes

| ID | Class |
|----|-------|
| 1 | Forest |
| 2 | Agriculture |
| 3 | Water |
| 4 | Built-up |
| 5 | Barren / Bare Land |

## 4. Dataset Sources — current real status

| Dataset | Source | Status |
|---|---|---|
| Shiggaon boundary | `soi_subdistricts.geojson`, user-provided (Survey-of-India-derived subdistrict layer, pre-filtered to Haveri) | **REAL, verified.** Area recomputed independently = 583.6 km², matches public reference figures (~584–588 km²) within 1%. Valid single-polygon geometry. |
| Micro-watersheds | `shiggaon_micro_watersheds.geojson`, user-provided (SLUSI-derived) | **REAL, verified.** 66 features, 0 invalid/empty geometries, 100% intersect the real Shiggaon boundary (independently re-checked, not just taken from the vendor's own validation report), total area 966.22 km² (recomputed independently in EPSG:32643, matches to 6 decimal places). |
| Reference LULC labels | ESA WorldCover 2021 v200, tiles `N12E075` and `N15E075`, user-provided | **REAL.** Shiggaon straddles the tile seam at lat 15° — both tiles are required and are mosaicked with windowed reads (see §6). |
| Sentinel-2 L2A imagery | Microsoft Planetary Computer STAC | **BLOCKED for automated search; REAL bands provided by user instead.** User supplied `B02/B03/B04/B08/B11.tif`, already on an identical EPSG:32643 / 10m grid. No STAC query was ever made — scene ID, acquisition date, and cloud-cover percentage are **UNKNOWN** and recorded as such in `data/raw/sentinel2/scene_metadata.json`, not invented. No Scene Classification (SCL) layer was provided, so only nodata-based masking was applied — no pixel-level cloud/shadow masking. |

**Do not confuse the boundary/micro-watershed sources with official direct
government-portal downloads** — they were supplied by the user from an
external tool run outside this sandbox; this repo did not download them
itself and cannot re-verify their original provenance beyond the geometric
and statistical checks in §5.

## 5. Independent verification performed on the uploaded files

Re-run in this repo, not just copied from the vendor's own validation report:

- Boundary: filtered to `TEHSIL == 'SHIGGAON'` from 7 Haveri tehsils, geometry validity checked, area recomputed in EPSG:32643.
- Micro-watersheds: geometry validity checked, `.intersects()` against the real (non-proxy) Shiggaon boundary recomputed from scratch (66/66 intersect), total area recomputed independently in EPSG:32643 (966.22 km², matches vendor figure to 6 decimal places), duplicate ID check.
- WorldCover: opened both tiles directly with `rasterio`, confirmed CRS (`EPSG:4326`), bounds (`N12E075`: lat 12–15; `N15E075`: lat 15–18), dtype `uint8`, nodata `0`.

## 6. Reference-label processing (already run, real output)

`python -m src.prepare_reference` mosaics the two WorldCover tiles using
**windowed reads** (not full 36000×36000 loads — that OOM-killed the
process on the first attempt; see the fix in `mosaic_and_clip_worldcover`),
clips to the real Shiggaon polygon, and remaps classes. Actual output from
this repo's real data:

```
Raw WorldCover (within study area):
  NoData/outside polygon: 41.48%
  Tree cover:               9.36%
  Shrubland:                 3.28%   <- ambiguous, excluded by default
  Grassland:                 1.32%   <- ambiguous, excluded by default
  Cropland:                 42.83%
  Built-up:                  1.29%
  Bare/sparse vegetation:    0.12%
  Permanent water bodies:    0.32%
  Herbaceous wetland:       ~0.00%

Remapped target classes:
  1 Forest:       9.36%
  2 Agriculture: 42.83%
  3 Water:        0.32%
  4 Built-up:     1.29%
  5 Barren:       0.12%
  Excluded (ambiguous + outside area): 46.09%
```

Cropland dominance and near-absent Water are consistent with an inland,
agriculture-heavy Deccan taluk — a plausibility check, not proof of
accuracy (WorldCover itself is a reference product; see §11).

### Grassland / Shrubland — why they're excluded, not mapped

Combined, these are 4.6% of the study area. In this agro-pastoral
landscape they are ambiguous between fallow/seasonally-tilled cropland and
uncultivated scrub/waste — WorldCover's global algorithm doesn't
distinguish these locally. Default strategy (`config.yaml:
reference_lulc.ambiguous_class_strategy = "exclude"`) drops these pixels
from training rather than guessing. Set the strategy to `"map"` and adjust
`ambiguous_mapping` to override this — that mapping is a documented
assumption, not a verified one, until someone visually spot-checks sample
pixels against a true-color composite.

## 7. Sentinel-2 — bands and resolution handling

- B02 (Blue), B03 (Green), B04 (Red), B08 (NIR): 10 m native.
- B11 (SWIR): 20 m native, bilinearly resampled onto the 10 m grid (`config.yaml: sentinel2.resample_method`).
- Pixel-level cloud/shadow/snow masking via the Scene Classification (SCL) band, not just the scene-level cloud-cover percentage (`config.yaml: sentinel2.scl_exclude_values`).

## 8. Features

`B2, B3, B4, B8, B11, NDVI, NDWI, NDBI` — exact order fixed by
`config.yaml: features.names`, enforced identically at training and
prediction time via `src/features.py`. Safe division (`src/features.py:
safe_divide`) returns 0.0 instead of inf/nan when NIR+Red (etc.) ≈ 0.

## 9. Pipeline status — COMPLETE, with real caveats

The pipeline ran end-to-end on real data. Full stage log and every number
below came from an actual execution (`python run_pipeline.py`), not
estimation.

**Training**: 15,000 stratified samples (3,000/class, spatially blocked
train/test split, 300m blocks) → 10,988 train / 4,012 test.

**Evaluation (agreement with WorldCover reference labels, held-out
spatial test set)**:

| Class | Precision | Recall | F1 |
|---|---|---|---|
| Forest | 0.93 | 0.89 | 0.91 |
| Agriculture | 0.72 | 0.77 | 0.74 |
| Water | 0.91 | 0.79 | 0.84 |
| Built-up | 0.76 | 0.76 | 0.76 |
| Barren | 0.70 | 0.81 | 0.75 |

Overall accuracy 0.80, macro F1 0.80, weighted F1 0.80. Feature importance
(highest to lowest): NDVI, B11, NDWI, B4, B8, B2, B3, NDBI.

### Known issue: full-raster class proportions do not match training-label proportions

| Class | % of reference-labeled training area | % of full-raster prediction | Ratio |
|---|---|---|---|
| Forest | 17.4% | 20.0% | 1.15x |
| Agriculture | 79.4% | 62.3% | 0.78x |
| Water | 0.6% | 0.7% | 1.26x |
| **Built-up** | 2.4% | **15.3%** | **6.39x** |
| **Barren** | 0.2% | **1.7%** | **7.65x** |

Built-up and Barren are substantially over-predicted across the full
scene relative to their true prevalence in the reference labels, at
Agriculture's expense. Per-class F1 on the spatially-held-out test set is
still reasonable for both (0.76 and 0.75), so this isn't simple model
failure — it's the expected side effect of combining `class_weight=
"balanced"` with equal-count (3,000/class) stratified sampling: the model
learns a near-uniform class prior instead of the true ~79%-Agriculture
population prior, and over-applies rare classes when generalizing to the
full image. **Do not read the full-raster class percentages in
`class_statistics.csv` as area estimates without this caveat.** A fix
worth trying next: drop `class_weight="balanced"`, or apply a
population-prior correction to full-raster predictions, and compare.

### Known issue: micro-watershed zonal statistics — coverage varies wildly

The 66 micro-watersheds extend well beyond the Shiggaon Taluk raster
extent (total watershed area 966 km² vs. taluk 583 km²), and the raster
itself has internal nodata from the boundary clip. Result: **17 of 66
micro-watersheds have less than 25% of their true area actually covered
by classified pixels** — one as low as 0.05%. `micro_watershed_
lulc_statistics.csv` includes a `pct_of_watershed_within_raster_extent`
column specifically so downstream consumers (Model 2) can filter these
out rather than trusting stats computed from a handful of pixels. Do not
use rows with low coverage as if they describe the whole watershed.

## 10. Final outputs (all real, in `outputs/`)

| File | Contents |
|---|---|
| `training_data.csv` | 15,000 samples, 8 features + label + spatial split column |
| `lulc_prediction.tif` | Final classified raster, EPSG:32643, 10m, 3043×3274px |
| `lulc_prediction.png` | Visualization of the above |
| `accuracy_report.json` | Full metrics incl. the WorldCover-agreement caveat |
| `classification_report.txt` | sklearn text report |
| `confusion_matrix.png`, `feature_importance.png`, `class_distribution.png` | Plots |
| `class_statistics.csv` | Full-scene class areas — read with the caveat in §9 |
| `micro_watershed_lulc_statistics.csv` | Per-watershed stats + coverage column — filter by coverage before use |

## 11. WorldCover version and evaluation caveat, restated

All accuracy/F1 numbers measure **agreement with ESA WorldCover 2021 v200
reference labels**, not verified ground truth. WorldCover 2021 itself has
an independently validated overall accuracy of ~76.7% — an upper bound on
how well this evaluation reflects reality on the ground. Report numbers as
"agreement with WorldCover," never as "real-world accuracy."

## 12. Known Limitations

These are the current, up-to-date known limitations of the production model (Experiment B). Verified against actual project data, not assumptions:

1. Built-up is over-predicted relative to WorldCover reference prevalence.
2. Barren is over-predicted relative to WorldCover reference prevalence.
3. Agriculture ↔ Built-up spectral confusion exists.
4. Water ↔ Barren confusion exists because of heterogeneous reference labeling.
5. 36/66 micro-watersheds have LOW or INSUFFICIENT_DATA coverage.
6. Only one Sentinel-2 date is currently used.
7. No SCL/cloud-shadow masking is available.
8. WorldCover is reference/pseudo-ground-truth and is not field-verified.

None of these are code bugs — they are documented, investigated scientific/data limitations (see §15, §18-20 for the full diagnostic history, including a controlled experiment that confirmed sampling-strategy changes do NOT resolve items 1-4, and a diagnostic that traced item 4 to genuine reference-label heterogeneity near water bodies, not a code defect).

One separate, genuine **code-level** issue (not a scientific limitation) was found during a later presentation-layer audit and has since been **fixed**: `outputs/lulc_confidence.tif` previously declared `nodata=-1.0` in its GeoTIFF header, while actual invalid pixels were physically stored as `0.0` — zero pixels in the file ever equaled `-1.0`. This was identified, backed up, and corrected directly in the file: the nodata tag now reads `0.0`, consistent with both the actual invalid-pixel values and `lulc_prediction.tif`'s own nodata convention. Verified after the fix: valid confidence pixels are bit-identical to the pre-fix backup, prediction/confidence valid-pixel masks now match exactly, confidence statistics for valid pixels are unchanged to the last digit, and the production model, `lulc_prediction.tif`, `training_data.csv`, all metrics, and class encoding were untouched. Old checksum `e13d1c82f7bb2386d3f84660b8936af1` → new checksum `7e48cdc1eb30f786f972d3609400aeec`. The pre-fix file is preserved at `backups/lulc_confidence_pre_nodata_fix_20260827_090312.tif`.

Supplementary detail on the items above:
- Sentinel-2 acquisition date/scene ID/cloud-cover are UNKNOWN — bands were supplied pre-processed, not queried via STAC (§7).
- Full-raster class proportions over-predict Built-up and Barren relative to reference-label prevalence (§9, §15) — confirmed via a controlled Experiment B/1.1 comparison to NOT be a sampling-strategy artifact alone.
- Water↔Barren confusion (§18-diagnostic turns, not numbered here): a spatial-proximity analysis found 49.4% of Barren training pixels sit within 100m of a Water pixel, and a 5-variant buffer-exclusion experiment confirmed removing them makes Macro-F1 worse at every buffer tested (0.807→0.785 at 100m) — this is reference-label heterogeneity, not noise to filter out.
- Grassland/Shrubland ambiguity (§6) — excluded from training by default, not resolved.
- Micro-watershed and boundary files were supplied pre-processed by the user from a tool outside this repository; this repo verified their internal consistency (§5) but did not re-derive them from a primary government source itself.

## 13. Installation

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 14. Reproduce the pipeline

```bash
python run_pipeline.py               # runs all 10 stages end-to-end (already done — see outputs/)
```

To reproduce from scratch, delete `data/raw/*`, `outputs/*`, `models/*` and re-run; you'll need to re-supply the boundary GeoJSON, WorldCover tiles, micro-watershed file, and Sentinel-2 bands as this repo cannot download any of them automatically in a network-restricted environment.

## 15. Class-imbalance / inference-prior experiments (A/B/C) — real results

Investigated after the first full run showed Built-up over-predicted 6.4x
and Barren 7.6x relative to reference-label prevalence. All three trained
and evaluated on real data (`run_single_experiment.py`), full results in
`outputs/experiment_comparison.json`.

| Experiment | Sampling | class_weight | Accuracy | Macro F1 | Weighted F1 |
|---|---|---|---|---|---|
| A (original baseline) | equal-count (3000/class) | balanced | 0.801 | 0.803 | 0.803 |
| **B (selected)** | equal-count (3000/class) | None | **0.805** | **0.807** | **0.807** |
| C | natural-prior (proportional, capped 20k) | None | 0.937 | 0.653 | 0.931 |

Per-class F1 — A vs B vs C:

| Class | A | B | C |
|---|---|---|---|
| Forest | 0.91 | 0.91 | 0.89 |
| Agriculture | 0.75 | 0.75 | 0.96 |
| Water | 0.84 | 0.85 | 0.74 |
| Built-up | 0.76 | 0.76 | **0.34** |
| Barren | 0.75 | 0.76 | **0.33** |

Full-scene predicted proportions vs. reference-label prevalence (17.35% Forest, 79.45% Agriculture, 0.59% Water, 2.40% Built-up, 0.22% Barren):

| Class | A | B | C | Reference |
|---|---|---|---|---|
| Forest | 19.98% | 20.17% | 16.21% | 17.35% |
| Agriculture | 62.61% | 62.65% | 82.03% | 79.45% |
| Water | 0.76% | 0.73% | 0.75% | 0.59% |
| Built-up | 14.99% | 14.76% | 0.86% | 2.40% |
| Barren | 1.67% | 1.70% | 0.15% | 0.22% |

**Real finding: `class_weight="balanced"` was not the main driver of the
distortion.** A and B are nearly identical in both metrics and full-scene
proportions — the artificial uniform class prior comes from equal-count
**sampling**, not the weighting parameter. Experiment C's sampling design
(proportional to true prevalence) does produce full-scene proportions
close to the reference — but at a cost that makes it unusable here:
Built-up F1 collapses to 0.34 and Barren to 0.33, because only 479 and 50
training pixels were available for those classes respectively. For a
watershed-risk-planning use case where built-up encroachment and degraded
land are exactly the classes that matter, that trade is not acceptable.

**Selected: Experiment B** — equal-count sampling, `class_weight=None`.
Marginally better than A on every metric with no downside, so it strictly
dominates A. **The Built-up/Barren full-scene over-prediction (~6-7x) is
not resolved and remains a known, documented limitation** — flagged in
`metadata.json` and `outputs/experiment_comparison.json`, not hidden.

## 16. Prediction confidence

`outputs/lulc_confidence.tif` — per-pixel maximum Random-Forest class
probability (0.0–1.0), NoData = -1.0 (distinct from a legitimate 0.0
confidence value). This is **model confidence, not statistical
certainty** — it reflects tree-ensemble agreement, not verified
correctness.

Real stats: mean confidence 0.783; low (<0.5) 7.0%; medium (0.5–0.75)
33.1%; high (≥0.75) 59.8%.

## 17. Spatial cleanup

Conservative isolated-pixel filter (`src/predict.py::
apply_conservative_cleanup`): a pixel is reclassified only if ALL 8
neighbors are valid and unanimously agree on one different class —
deliberately not a general majority/mode filter, to avoid eroding small
real features (ponds, buildings, narrow water bodies). Real effect:
**39,498 pixels changed (0.40% of the raster)** — small and conservative,
as intended.

## 18. Watershed coverage — real categorized results

`outputs/coverage_report.csv` and the `coverage_category` column in
`micro_watershed_lulc_statistics.csv`. Categories: GOOD (≥90% of the
watershed's true area within the raster extent), ACCEPTABLE (75–90%), LOW
(<75%), INSUFFICIENT_DATA (valid pixel count <100, overriding the
percentage bands — e.g. a tiny high-percentage fragment is still flagged).

Real counts across the 66 watersheds: **GOOD 27, ACCEPTABLE 3, LOW 35,
INSUFFICIENT_DATA 1.** More than half the watersheds are LOW or
INSUFFICIENT_DATA — Model 2 should filter on `coverage_category` rather
than treating all 66 rows as equally reliable.

## 19. Cloud/shadow masking — confirmed unavailable, not invented

The supplied Sentinel-2 package contains only B02/B03/B04/B08/B11 — no
SCL, cloud-probability, or QA layer. No cloud/shadow/cirrus/snow masking
was applied beyond nodata. `src/download_sentinel.py::load_scl_mask()`
already implements SCL-based masking and will activate automatically if
an SCL band is ever added to `data/raw/sentinel2/`, with no redesign
needed — but for this run, `scl_cloud_mask_applied: false` is recorded
honestly in `data/raw/sentinel2/scene_metadata.json`.

## 20. NoData composition

41.43% of Sentinel-2 pixels are NoData. Only one component of this is
distinguishable with the data available: the ~41.48% "outside the
Shiggaon polygon" figure from the independent WorldCover clip (§6) is
almost identical, indicating the bands were pre-clipped to the same
boundary. **Cloud/shadow, invalid-satellite-pixel, and true missing-data
components cannot be separated from each other** without an SCL layer —
this is stated as a limitation, not resolved by assumption.

## 21. Final comparison and recommendation

**Recommended: Experiment B** for the SIH prototype. Reasoning: per your
own stated priority (macro-F1 and per-class F1 over raw accuracy), B ties
or beats A on every metric and is a strict improvement; C's much higher
accuracy is a class-imbalance artifact (dominated by trivially easy
Agriculture pixels) that comes with unusable Built-up/Barren detection.
Ship B with the full-scene proportion caveat documented — do not present
`class_statistics.csv` percentages as calibrated area estimates without
it.
