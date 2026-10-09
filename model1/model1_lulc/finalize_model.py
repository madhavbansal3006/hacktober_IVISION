"""
Finalize Model 1 using the selected experiment (B: equal-count sampling,
class_weight=None) — generate the full-raster prediction, confidence
map, conservative cleanup, zonal statistics with coverage categories,
metadata.json, classification_report.csv, and run output validation.

Run after cache_shared_inputs.py and run_single_experiment.py B have
already produced data/processed/features/shared_inputs_cache.pkl and
models/lulc_random_forest.joblib.
"""
from __future__ import annotations

import json
import os
import pickle
import platform
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.config import load_config, ensure_dirs
from src.predict import (
    predict_full_raster, write_prediction_geotiff, write_confidence_geotiff,
    summarize_confidence, apply_conservative_cleanup,
)
from src.zonal_statistics import load_micro_watersheds, compute_zonal_stats, classify_coverage

CACHE_PATH = "data/processed/features/shared_inputs_cache.pkl"
SELECTED_EXPERIMENT = "B_equal_count_unweighted"


def main():
    cfg = load_config()
    ensure_dirs(cfg)
    t0 = time.time()

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    feature_array = cache["feature_array"]
    valid_mask = cache["valid_mask"]
    transform = cache["transform"]
    crs = cache["crs"]
    boundary_gdf = cache["boundary_gdf"]

    model = joblib.load(cfg["paths"]["model_path"])
    print(f"Loaded model from {cfg['paths']['model_path']}")

    print("Predicting full raster with confidence (chunked to bound memory)...")
    rows, cols, n_feat = feature_array.shape
    flat_features = feature_array.reshape(-1, n_feat)
    flat_valid = valid_mask.reshape(-1)
    valid_idx = np.where(flat_valid)[0]

    pred_flat = np.zeros(flat_valid.shape[0], dtype=np.uint8)
    conf_flat = np.zeros(flat_valid.shape[0], dtype=np.float32)
    chunk = 500_000
    for start in range(0, len(valid_idx), chunk):
        idx_chunk = valid_idx[start:start + chunk]
        proba = model.predict_proba(flat_features[idx_chunk])
        cls_idx = np.argmax(proba, axis=1)
        pred_flat[idx_chunk] = model.classes_[cls_idx].astype(np.uint8)
        conf_flat[idx_chunk] = proba[np.arange(len(proba)), cls_idx].astype(np.float32)
    prediction_raster = pred_flat.reshape(rows, cols)
    confidence_raster = conf_flat.reshape(rows, cols)
    print(f"  Done at {time.time()-t0:.1f}s")

    conf_stats = summarize_confidence(confidence_raster, valid_mask)
    print("Confidence stats:", conf_stats)

    print("Applying conservative isolated-pixel cleanup...")
    cleaned_raster, cleanup_stats = apply_conservative_cleanup(prediction_raster, cfg["nodata_value"])
    print("Cleanup stats:", cleanup_stats)

    write_prediction_geotiff(cleaned_raster, transform, crs, cfg["paths"]["prediction_tif"], cfg["nodata_value"])
    write_confidence_geotiff(confidence_raster, transform, crs, cfg["paths"]["prediction_png"].replace(
        "lulc_prediction.png", "lulc_confidence.tif"))

    # class_statistics.csv (from cleaned raster)
    target_classes = cfg["target_classes"]
    pixel_area_ha = abs(transform.a * transform.e) / 10000
    total_classified = int((cleaned_raster != 0).sum())
    rows_cs = []
    for cid, name in target_classes.items():
        px = int((cleaned_raster == cid).sum())
        rows_cs.append({
            "class_id": cid, "class_name": name, "pixel_count": px,
            "area_ha": px * pixel_area_ha, "area_km2": px * pixel_area_ha / 100,
            "percent_of_classified_area": 100 * px / total_classified if total_classified else 0,
        })
    class_stats_df = pd.DataFrame(rows_cs)
    class_stats_df.to_csv(cfg["paths"]["class_statistics_csv"], index=False)
    print(f"Wrote {cfg['paths']['class_statistics_csv']}")

    # Zonal statistics with coverage categories
    print("Computing zonal statistics with coverage quality categories...")
    mw_gdf = load_micro_watersheds(cfg)
    stats_df = compute_zonal_stats(cfg["paths"]["prediction_tif"], mw_gdf, target_classes,
                                    cfg["micro_watersheds"]["id_field"])

    # Recompute valid_pixel_count and coverage category per watershed (needs the raster again for pixel counts)
    import rasterio
    from rasterio.mask import mask as rio_mask
    valid_pixel_counts = []
    with rasterio.open(cfg["paths"]["prediction_tif"]) as src:
        mw_reproj = mw_gdf.to_crs(src.crs)
        for idx, poly_row in mw_reproj.iterrows():
            try:
                out_image, _ = rio_mask(src, [poly_row.geometry.__geo_interface__], crop=True, nodata=0)
                valid_pixel_counts.append(int((out_image[0] != 0).sum()))
            except ValueError:
                valid_pixel_counts.append(0)
    stats_df["valid_pixel_count"] = valid_pixel_counts
    stats_df["coverage_category"] = [
        classify_coverage(pct, vpc) for pct, vpc in
        zip(stats_df["pct_of_watershed_within_raster_extent"], stats_df["valid_pixel_count"])
    ]
    stats_df.to_csv(cfg["paths"]["micro_watershed_stats_csv"], index=False)
    print(f"Wrote {cfg['paths']['micro_watershed_stats_csv']}")
    print("Coverage category counts:", stats_df["coverage_category"].value_counts().to_dict())

    # coverage_report.csv — dedicated summary
    coverage_report = stats_df[[
        "micro_watershed_id", "source_area_km2", "total_area_ha",
        "pct_of_watershed_within_raster_extent", "valid_pixel_count", "coverage_category"
    ]].copy()
    coverage_report_path = "outputs/coverage_report.csv"
    coverage_report.to_csv(coverage_report_path, index=False)
    print(f"Wrote {coverage_report_path}")

    # classification_report.csv (from the experiment comparison JSON, selected experiment)
    with open("outputs/experiment_comparison.json") as f:
        exp_data = json.load(f)
    selected = next(e for e in exp_data["experiments"] if e["experiment"] == SELECTED_EXPERIMENT)
    cr_rows = []
    for cls_name, m in selected["per_class"].items():
        cr_rows.append({"class": cls_name, "precision": m["precision"], "recall": m["recall"],
                         "f1_score": m["f1"], "support": m["support"]})
    cr_rows.append({"class": "accuracy", "precision": "", "recall": "", "f1_score": selected["accuracy"],
                     "support": selected["n_test_samples"]})
    cr_rows.append({"class": "macro avg", "precision": "", "recall": "", "f1_score": selected["macro_f1"],
                     "support": selected["n_test_samples"]})
    cr_rows.append({"class": "weighted avg", "precision": "", "recall": "", "f1_score": selected["weighted_f1"],
                     "support": selected["n_test_samples"]})
    pd.DataFrame(cr_rows).to_csv("outputs/classification_report.csv", index=False)
    print("Wrote outputs/classification_report.csv")

    # metadata.json
    n_low_cov = int((stats_df["coverage_category"] == "LOW").sum())
    n_insufficient = int((stats_df["coverage_category"] == "INSUFFICIENT_DATA").sum())
    metadata = {
        "satellite": "UNKNOWN (bands provided pre-processed, no STAC query performed)",
        "product": "UNKNOWN",
        "acquisition_date": "UNKNOWN",
        "tile": "UNKNOWN",
        "cloud_percentage": "UNKNOWN (no SCL/QA layer provided; only nodata masking applied)",
        "crs": str(crs),
        "resolution_m": abs(transform.a),
        "bands_used": list(cfg["sentinel2"]["bands"].values()),
        "indices": ["NDVI", "NDWI", "NDBI", "BSI"],
        "classifier": "RandomForestClassifier",
        "selected_experiment": SELECTED_EXPERIMENT,
        "hyperparameters": {
            "n_estimators": cfg["random_forest"]["n_estimators"],
            "class_weight": None,
            "random_state": cfg["random_forest"]["random_state"],
            "n_jobs": cfg["random_forest"]["n_jobs"],
        },
        "sampling_strategy": "equal_count, 3000 samples/class, spatial block split (300m blocks, 25% test)",
        "n_training_samples": selected["n_train_samples"],
        "n_validation_samples": selected["n_test_samples"],
        "evaluation_metrics": {
            "accuracy": selected["accuracy"], "macro_f1": selected["macro_f1"],
            "weighted_f1": selected["weighted_f1"], "per_class": selected["per_class"],
        },
        "full_scene_predicted_class_percent": selected["full_scene_predicted_percent"],
        "reference_label_prevalence_percent": exp_data["reference_label_prevalence_percent"],
        "cloud_shadow_masking": "UNAVAILABLE — no SCL/QA layer provided with the Sentinel-2 bands",
        "confidence_stats": conf_stats,
        "spatial_cleanup": cleanup_stats,
        "watershed_coverage": {
            "total_watersheds": len(stats_df), "low_coverage_count": n_low_cov,
            "insufficient_data_count": n_insufficient,
        },
        "class_encoding": target_classes,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "important_note": (
            "All evaluation metrics measure agreement with ESA WorldCover 2021 v200 reference "
            "labels (a global reference product, ~76.7% independently validated accuracy), NOT "
            "field-verified ground truth. Full-scene predicted class percentages should not be "
            "read as area estimates without accounting for the known equal-count-sampling class "
            "prior distortion documented in outputs/experiment_comparison.json."
        ),
    }
    with open("outputs/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print("Wrote outputs/metadata.json")

    print(f"\nTotal finalize time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
