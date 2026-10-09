# Model 1 — Shiggaon LULC Classification

## Production Model
- Model: Random Forest
- Production experiment: Experiment B
- Model file: models/lulc_random_forest.joblib
- n_estimators: 200
- class_weight: None
- random_state: 42

## Class Encoding
1 = Forest
2 = Agriculture
3 = Water
4 = Built-up
5 = Barren

## Validation Metrics
- Accuracy: 0.8051
- Macro-F1: 0.8066
- Weighted-F1: 0.8073

## Per-Class F1
- Forest: 0.91
- Agriculture: 0.75
- Water: 0.85
- Built-up: 0.76
- Barren: 0.76

## Study Area
- Shiggaon Taluk
- Haveri district
- Karnataka, India
- 66 micro-watersheds

## Main Data
- Shiggaon boundary:
  - Original boundary source: soi_subdistricts.geojson
  - Repository boundary file: data/raw/study_area/shiggaon_boundary.gpkg
  - The GeoPackage is the actual boundary file included in this repository.
- Micro-watersheds: 66 real SLUSI micro-watersheds
- Sentinel-2 bands: B02, B03, B04, B08, B11
- ESA WorldCover 2021 reference labels

## Outputs
- lulc_prediction.tif
- lulc_confidence.tif
- training_data.csv
- classification_report.csv
- confusion_matrix
- coverage_report.csv
- micro_watershed_lulc_statistics.csv
- metadata.json

## Validation
- 31/31 tests passed

## Known Limitations
1. Built-up is over-predicted compared with WorldCover reference prevalence.
2. Barren is over-predicted compared with WorldCover reference prevalence.
3. 36/66 micro-watersheds have LOW or INSUFFICIENT coverage.
4. ESA WorldCover is used as reference/pseudo-ground-truth and is not field-verified ground truth.
5. No Sentinel-2 SCL/cloud-shadow masking is currently available.
6. The model currently uses a single Sentinel-2 acquisition.
7. Agriculture and Built-up have genuine spectral overlap.
8. Water and Barren have reference-label heterogeneity.

## Important
Experiment B is the current production baseline and must not be overwritten without a documented comparison against the existing baseline.
Do not fabricate or change any metrics.
