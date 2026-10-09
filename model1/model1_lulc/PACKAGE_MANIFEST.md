# Model 1 — Package Manifest

Generated at packaging time. Lists every file included in Model1_Shiggaon_LULC_Final.zip.

| File | Size (KB) | Purpose | Required for demo | Production output |
|---|---|---|---|---|
| .gitignore | 0.2 | Git ignore rules | No | No |
| PROJECT_DATA_MANIFEST.md | 1.9 | Quick-reference production summary | Yes | No |
| README.md | 18.9 | Full project documentation | Yes | No |
| cache_shared_inputs.py | 2.1 | Pipeline orchestration/experiment script | No | No |
| config.yaml | 7.4 | Central pipeline configuration | Yes | No |
| data/processed/features/worldcover_remapped.tif | 321.8 | Processed WorldCover reference-label raster (clipped+remapped, small — raw source tiles excluded) | No | No |
| data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg | 196.0 | Required 66 real SLUSI micro-watershed polygons | Yes | No |
| data/raw/sentinel2/B02.tif | 9740.2 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/sentinel2/B03.tif | 9917.3 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/sentinel2/B04.tif | 10727.5 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/sentinel2/B08.tif | 11098.3 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/sentinel2/B11.tif | 12745.9 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/sentinel2/scene_metadata.json | 0.3 | Required Sentinel-2 L2A band (input to the pipeline) | Yes | No |
| data/raw/study_area/shiggaon_boundary.gpkg | 120.0 | Required Shiggaon Taluk boundary (real, verified) | Yes | No |
| finalize_model.py | 9.6 | Pipeline orchestration/experiment script | No | No |
| generate_demo_report.py | 7.6 | Pipeline orchestration/experiment script | No | No |
| models/lulc_random_forest.joblib | 54372.9 | Production trained Random Forest model (Experiment B, n_estimators=200, class_weight=None, random_state=42) | Yes | Yes |
| models/model_metadata.json | 0.8 | Model training metadata | Yes | Yes |
| outputs/barren_buffer/comparison_report.json | 11.5 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/barren_buffer/training_data_buffer_100m.csv | 1137.6 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/barren_buffer/training_data_buffer_20m.csv | 1255.4 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/barren_buffer/training_data_buffer_30m.csv | 1230.7 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/barren_buffer/training_data_buffer_50m.csv | 1184.1 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/barren_buffer/training_data_buffer_75m.csv | 1149.6 | Barren-buffer filtering experiment results (all 5 variants REJECTED, kept as documented negative result) | No | No |
| outputs/class_statistics.csv | 0.3 | PRODUCTION full-scene class area/percentage breakdown | Yes | Yes |
| outputs/classification_report.csv | 0.5 | PRODUCTION per-class precision/recall/F1 | Yes | Yes |
| outputs/confusion_matrix.png | 60.7 | PRODUCTION 5x5 confusion matrix visualization | Yes | Yes |
| outputs/coverage_report.csv | 3.5 | PRODUCTION micro-watershed coverage quality report | Yes | Yes |
| outputs/demo_report.json | 3.3 | Presentation-layer summary report (confidence, coverage, limitations) | Yes | No |
| outputs/demo_report.md | 1.3 | Presentation-layer summary report (confidence, coverage, limitations) | Yes | No |
| outputs/experiment_comparison.json | 6.4 | Experiment A/B/C comparison results (documents why B was selected) | Yes | No |
| outputs/lulc_confidence.png | 1703.9 | Visualization of lulc_confidence.tif | Yes | Yes |
| outputs/lulc_confidence.tif | 9548.4 | PRODUCTION per-pixel prediction confidence raster (nodata=0.0, fixed encoding) | Yes | Yes |
| outputs/lulc_prediction.png | 1434.1 | Visualization of lulc_prediction.tif | Yes | Yes |
| outputs/lulc_prediction.tif | 893.0 | PRODUCTION final classified LULC raster (1-5=classes, 0=NoData, EPSG:32643, 10m) | Yes | Yes |
| outputs/metadata.json | 4.2 | PRODUCTION full run metadata (metrics, hyperparameters, limitations, provenance) | Yes | Yes |
| outputs/micro_watershed_lulc_statistics.csv | 12.8 | PRODUCTION per-watershed LULC statistics (66 watersheds, coverage-flagged) | Yes | Yes |
| outputs/model1_v1_1/comparison_report.json | 3.2 | Model 1.1 experiment artifacts (REJECTED candidate, kept as documented negative result) | No | No |
| outputs/model1_v1_1/confusion_matrix_v1_1.png | 59.5 | Model 1.1 experiment artifacts (REJECTED candidate, kept as documented negative result) | No | No |
| outputs/model1_v1_1/lulc_confidence_v1_1.tif | 9599.0 | Model 1.1 experiment artifacts (REJECTED candidate, kept as documented negative result) | No | No |
| outputs/model1_v1_1/lulc_prediction_v1_1.tif | 759.3 | Model 1.1 experiment artifacts (REJECTED candidate, kept as documented negative result) | No | No |
| outputs/model1_v1_1/training_data_v1_1.csv | 2064.5 | Model 1.1 experiment artifacts (REJECTED candidate, kept as documented negative result) | No | No |
| outputs/training_data.csv | 1727.2 | PRODUCTION training sample table (15,000 rows, 9 features + label + split) | Yes | Yes |
| requirements.txt | 0.2 | Python dependencies | Yes | No |
| run_barren_buffer_experiment.py | 10.7 | Pipeline orchestration/experiment script | No | No |
| run_experiments.py | 8.2 | Pipeline orchestration/experiment script | No | No |
| run_model_1_1.py | 9.6 | Pipeline orchestration/experiment script | No | No |
| run_pipeline.py | 6.3 | Pipeline orchestration/experiment script | No | No |
| run_single_experiment.py | 5.9 | Pipeline orchestration/experiment script | No | No |
| src/__init__.py | 0.0 | Pipeline source code module | Yes | No |
| src/config.py | 2.8 | Pipeline source code module | Yes | No |
| src/demo_report.py | 8.3 | Pipeline source code module | Yes | No |
| src/download_sentinel.py | 11.6 | Pipeline source code module | Yes | No |
| src/evaluate.py | 6.3 | Pipeline source code module | Yes | No |
| src/features.py | 3.0 | Pipeline source code module | Yes | No |
| src/predict.py | 8.5 | Pipeline source code module | Yes | No |
| src/prepare_reference.py | 11.1 | Pipeline source code module | Yes | No |
| src/prepare_study_area.py | 7.2 | Pipeline source code module | Yes | No |
| src/preprocess.py | 2.2 | Pipeline source code module | Yes | No |
| src/sampling.py | 9.7 | Pipeline source code module | Yes | No |
| src/train.py | 5.0 | Pipeline source code module | Yes | No |
| src/validate_output.py | 6.8 | Pipeline source code module | Yes | No |
| src/zonal_statistics.py | 6.4 | Pipeline source code module | Yes | No |
| tests/__init__.py | 0.0 | Test suite (42 tests) | No | No |
| tests/test_demo_report.py | 5.2 | Test suite (42 tests) | No | No |
| tests/test_features.py | 2.8 | Test suite (42 tests) | No | No |
| tests/test_labels.py | 3.0 | Test suite (42 tests) | No | No |
| tests/test_output.py | 3.1 | Test suite (42 tests) | No | No |
| tests/test_upgrades.py | 4.8 | Test suite (42 tests) | No | No |

**Total: 68 files, 146.7 MB**
