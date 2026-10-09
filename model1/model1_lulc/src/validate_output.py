"""
Upgraded programmatic validation of Model 1's final outputs:
lulc_prediction.tif, lulc_confidence.tif, and the required output-file
set / metadata.json.

Run standalone: python -m src.validate_output
"""
from __future__ import annotations

import json
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio

from src.config import load_config

REQUIRED_OUTPUT_FILES = [
    "outputs/lulc_prediction.tif",
    "outputs/lulc_confidence.tif",
    "outputs/training_data.csv",
    "outputs/classification_report.csv",
    "outputs/confusion_matrix.png",
    "outputs/coverage_report.csv",
    "outputs/micro_watershed_lulc_statistics.csv",
    "outputs/metadata.json",
]


class ValidationError(RuntimeError):
    pass


def validate_prediction_geotiff(tif_path: str, cfg: dict, boundary_gdf=None) -> dict:
    results = {}
    try:
        src = rasterio.open(tif_path)
    except Exception as e:
        raise ValidationError(f"Raster failed to open: {type(e).__name__}: {e}")
    results["opens_successfully"] = True

    if src.crs is None:
        raise ValidationError("CRS is missing.")
    results["crs"] = str(src.crs)

    if src.transform is None or src.transform.is_identity:
        raise ValidationError("Transform is missing or identity (unreferenced).")
    results["resolution_m"] = (abs(src.transform.a), abs(src.transform.e))
    results["width"], results["height"] = src.width, src.height
    results["bounds"] = tuple(src.bounds)
    results["nodata"] = src.nodata

    arr = src.read(1)
    valid_pixels = arr[arr != (src.nodata if src.nodata is not None else 255)]
    unique_values = set(np.unique(valid_pixels).tolist())
    expected_values = set(cfg["target_classes"].keys())
    unexpected = unique_values - expected_values
    if unexpected:
        raise ValidationError(f"Unexpected class values outside {sorted(expected_values)}: {sorted(unexpected)}")
    results["unique_class_values"] = sorted(unique_values)
    results["valid_pixel_count"] = int((arr != 0).sum())
    results["class_pixel_counts"] = {int(v): int((arr == v).sum()) for v in sorted(np.unique(arr))}

    if boundary_gdf is not None:
        from shapely.geometry import box
        raster_bbox = box(*src.bounds)
        boundary_reproj = boundary_gdf.to_crs(src.crs)
        if not boundary_reproj.geometry.intersects(raster_bbox).any():
            raise ValidationError("Raster does not overlap the Shiggaon boundary.")
        results["overlaps_study_area_boundary"] = True

    src.close()
    return results


def validate_confidence_geotiff(tif_path: str) -> dict:
    results = {}
    try:
        src = rasterio.open(tif_path)
    except Exception as e:
        raise ValidationError(f"Confidence raster failed to open: {type(e).__name__}: {e}")
    results["opens_successfully"] = True
    results["crs"] = str(src.crs)
    arr = src.read(1)
    valid = arr[arr != src.nodata] if src.nodata is not None else arr

    if np.isnan(valid).any():
        raise ValidationError("Confidence raster contains unexpected NaN values in valid pixels.")
    if valid.size > 0 and (valid.min() < 0.0 or valid.max() > 1.0):
        raise ValidationError(
            f"Confidence values outside [0,1]: min={valid.min()}, max={valid.max()}"
        )
    results["min_confidence"] = float(valid.min()) if valid.size else None
    results["max_confidence"] = float(valid.max()) if valid.size else None
    src.close()
    return results


def validate_required_files() -> dict:
    missing = [p for p in REQUIRED_OUTPUT_FILES if not os.path.exists(p)]
    if missing:
        raise ValidationError(f"Missing required output files: {missing}")
    return {"all_required_files_present": True, "files": REQUIRED_OUTPUT_FILES}


def validate_metadata_json(path: str = "outputs/metadata.json") -> dict:
    if not os.path.exists(path):
        raise ValidationError(f"{path} does not exist.")
    with open(path) as f:
        meta = json.load(f)
    required_keys = [
        "satellite", "product", "acquisition_date", "tile", "cloud_percentage",
        "crs", "resolution_m", "bands_used", "indices", "classifier",
        "hyperparameters", "n_training_samples", "n_validation_samples",
        "evaluation_metrics", "class_encoding",
    ]
    missing_keys = [k for k in required_keys if k not in meta]
    if missing_keys:
        raise ValidationError(f"metadata.json missing required keys: {missing_keys}")
    return {"metadata_valid": True, "keys_present": list(meta.keys())}


def validate_watershed_coverage(csv_path: str, min_valid_pixels: int = 100) -> dict:
    import pandas as pd
    if not os.path.exists(csv_path):
        raise ValidationError(f"{csv_path} does not exist.")
    df = pd.read_csv(csv_path)
    required_cols = {"micro_watershed_id", "coverage_category", "valid_pixel_count"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValidationError(f"Coverage CSV missing columns: {missing_cols}")

    below_threshold_but_not_flagged = df[
        (df["valid_pixel_count"] < min_valid_pixels) & (df["coverage_category"] != "INSUFFICIENT_DATA")
    ]
    if len(below_threshold_but_not_flagged) > 0:
        raise ValidationError(
            f"{len(below_threshold_but_not_flagged)} watersheds have valid_pixel_count < "
            f"{min_valid_pixels} but are NOT flagged INSUFFICIENT_DATA — categorization bug."
        )
    return {
        "n_watersheds": len(df),
        "category_counts": df["coverage_category"].value_counts().to_dict(),
        "min_valid_pixel_threshold_enforced": min_valid_pixels,
    }


if __name__ == "__main__":
    cfg = load_config()
    all_results = {}
    failed = False

    boundary_gdf = None
    try:
        from src.prepare_study_area import load_shiggaon_boundary
        boundary_gdf, is_real = load_shiggaon_boundary(cfg)
    except Exception as e:
        print(f"WARNING: could not load boundary for overlap check: {e}")

    checks = [
        ("Required output files", lambda: validate_required_files()),
        ("Prediction GeoTIFF", lambda: validate_prediction_geotiff(cfg["paths"]["prediction_tif"], cfg, boundary_gdf)),
        ("Confidence GeoTIFF", lambda: validate_confidence_geotiff("outputs/lulc_confidence.tif")),
        ("metadata.json", lambda: validate_metadata_json()),
        ("Watershed coverage categorization", lambda: validate_watershed_coverage(cfg["paths"]["micro_watershed_stats_csv"])),
    ]

    for name, fn in checks:
        try:
            result = fn()
            print(f"[PASS] {name}")
            for k, v in result.items():
                print(f"    {k}: {v}")
            all_results[name] = {"status": "PASS", **result}
        except ValidationError as e:
            print(f"[FAIL] {name}: {e}")
            all_results[name] = {"status": "FAIL", "error": str(e)}
            failed = True

    print("\n" + ("VALIDATION FAILED" if failed else "ALL VALIDATION CHECKS PASSED"))
    sys.exit(1 if failed else 0)
