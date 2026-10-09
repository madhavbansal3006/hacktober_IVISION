"""
Apply the trained Random Forest to every valid pixel of the Shiggaon study
area and write a georeferenced classified GeoTIFF.

The model operates on (n_pixels, n_features) internally, as scikit-learn
requires, but the (row, col) position of every pixel is tracked explicitly
so the flat prediction array is reconstructed into (rows, cols) using the
ORIGINAL raster transform before writing — spatial information is never
permanently lost.
"""
from __future__ import annotations

import os

import joblib
import numpy as np
import rasterio

from src.config import load_config, ensure_dirs


def predict_full_raster(
    model,
    feature_array: np.ndarray,   # (rows, cols, n_features)
    valid_mask: np.ndarray,      # (rows, cols) bool
    nodata_value: int,
) -> np.ndarray:
    """Predict class labels for every valid pixel and reconstruct a full
    (rows, cols) uint8 raster, with nodata_value everywhere invalid.
    """
    rows, cols, n_features = feature_array.shape
    flat_features = feature_array.reshape(-1, n_features)
    flat_valid = valid_mask.reshape(-1)

    predictions_flat = np.full(flat_valid.shape[0], nodata_value, dtype=np.uint8)

    if flat_valid.sum() == 0:
        raise ValueError("No valid pixels to predict — valid_mask is entirely False.")

    predictions_flat[flat_valid] = model.predict(flat_features[flat_valid]).astype(np.uint8)

    # Reconstruct spatial structure — this is the essential row/col mapping step.
    prediction_raster = predictions_flat.reshape(rows, cols)
    return prediction_raster


def predict_full_raster(
    model,
    feature_array: np.ndarray,   # (rows, cols, n_features)
    valid_mask: np.ndarray,      # (rows, cols) bool
    nodata_value: int,
    return_confidence: bool = False,
):
    """Predict class labels for every valid pixel and reconstruct a full
    (rows, cols) uint8 raster, with nodata_value everywhere invalid.

    If return_confidence=True, also returns a (rows, cols) float32 array
    of the model's maximum predicted-class probability per pixel (0.0
    everywhere invalid). This is model confidence/probability, NOT a
    statistical certainty guarantee — it reflects how consistently the
    Random Forest's trees agree, not ground-truth correctness.
    """
    rows, cols, n_features = feature_array.shape
    flat_features = feature_array.reshape(-1, n_features)
    flat_valid = valid_mask.reshape(-1)

    predictions_flat = np.full(flat_valid.shape[0], nodata_value, dtype=np.uint8)
    confidence_flat = np.zeros(flat_valid.shape[0], dtype=np.float32) if return_confidence else None

    if flat_valid.sum() == 0:
        raise ValueError("No valid pixels to predict — valid_mask is entirely False.")

    if return_confidence:
        proba = model.predict_proba(flat_features[flat_valid])
        class_indices = np.argmax(proba, axis=1)
        predictions_flat[flat_valid] = model.classes_[class_indices].astype(np.uint8)
        confidence_flat[flat_valid] = proba[np.arange(len(proba)), class_indices].astype(np.float32)
    else:
        predictions_flat[flat_valid] = model.predict(flat_features[flat_valid]).astype(np.uint8)

    prediction_raster = predictions_flat.reshape(rows, cols)
    if return_confidence:
        confidence_raster = confidence_flat.reshape(rows, cols)
        return prediction_raster, confidence_raster
    return prediction_raster


def write_confidence_geotiff(confidence_raster: np.ndarray, transform, crs, out_path: str):
    """Write the per-pixel max-class-probability raster. NoData pixels
    (confidence 0.0, which is also a legitimate low-confidence value) are
    distinguished by a separate nodata sentinel (-1.0) so 0.0 confidence
    is never confused with "no prediction made".
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out = confidence_raster.copy()
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "height": out.shape[0], "width": out.shape[1],
        "crs": crs, "transform": transform, "nodata": -1.0, "compress": "lzw",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(out, 1)
    print(f"Wrote confidence GeoTIFF to {out_path}")


def summarize_confidence(confidence_raster: np.ndarray, valid_mask: np.ndarray) -> dict:
    """Mean confidence and low/medium/high-confidence pixel percentages,
    computed only over valid (classified) pixels.
    Thresholds: low <0.5, medium 0.5-0.75, high >=0.75 — reasonable
    defaults for a 5-class RF, not empirically tuned.
    """
    vals = confidence_raster[valid_mask]
    if vals.size == 0:
        return {"mean_confidence": None, "low_pct": None, "medium_pct": None, "high_pct": None}
    return {
        "mean_confidence": float(vals.mean()),
        "low_confidence_pct": float(100 * (vals < 0.5).sum() / vals.size),
        "medium_confidence_pct": float(100 * ((vals >= 0.5) & (vals < 0.75)).sum() / vals.size),
        "high_confidence_pct": float(100 * (vals >= 0.75).sum() / vals.size),
        "thresholds": {"low": "<0.5", "medium": "0.5-0.75", "high": ">=0.75"},
    }


def apply_conservative_cleanup(prediction_raster: np.ndarray, nodata_value: int) -> tuple[np.ndarray, dict]:
    """Remove only true salt-and-pepper single-pixel noise: a pixel is
    reclassified ONLY if ALL 8 of its neighbors are valid and share one
    single class different from the center pixel's class. Deliberately
    conservative — does NOT apply a general majority/mode filter, which
    would erode small legitimate features (ponds, buildings, narrow water
    bodies, small field boundaries). NoData is never touched and never
    used to outvote a real class. Vectorized via convolution (not a
    per-pixel Python loop, which would be far too slow at ~10M pixels).

    Returns (cleaned_raster, stats dict).
    """
    from scipy.ndimage import convolve

    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
    valid = (prediction_raster != nodata_value).astype(np.uint8)
    valid_neighbor_count = convolve(valid, kernel, mode="constant", cval=0)

    class_ids = sorted(int(c) for c in np.unique(prediction_raster) if c != nodata_value)
    same_class_neighbor_count = {}
    for c in class_ids:
        class_mask = (prediction_raster == c).astype(np.uint8)
        same_class_neighbor_count[c] = convolve(class_mask, kernel, mode="constant", cval=0)

    out = prediction_raster.copy()
    all_neighbors_valid = valid_neighbor_count == 8
    n_changed = 0
    for c in class_ids:
        # Pixels where all 8 neighbors are valid AND all 8 agree on class c AND center != c.
        unanimous_c = all_neighbors_valid & (same_class_neighbor_count[c] == 8) & (prediction_raster != c) \
                      & (prediction_raster != nodata_value)
        n = int(unanimous_c.sum())
        if n > 0:
            out[unanimous_c] = c
            n_changed += n

    stats = {
        "n_pixels_changed": int(n_changed),
        "pct_pixels_changed": float(100 * n_changed / prediction_raster.size),
        "method": "isolated-pixel-only: reclassify center only if ALL 8 neighbors are valid and "
                  "unanimously agree on one different class; never touches NoData; does not apply "
                  "a general mode filter (protects small legitimate features).",
    }
    return out, stats


def write_prediction_geotiff(
    prediction_raster: np.ndarray,
    transform,
    crs,
    out_path: str,
    nodata_value: int,
):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "count": 1,
        "height": prediction_raster.shape[0],
        "width": prediction_raster.shape[1],
        "crs": crs,
        "transform": transform,
        "nodata": nodata_value,
        "compress": "lzw",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(prediction_raster, 1)
    print(f"Wrote classified GeoTIFF to {out_path}")
    print(f"  Shape: {prediction_raster.shape}, CRS: {crs}, "
          f"resolution: {transform.a}m")

    unique, counts = np.unique(prediction_raster, return_counts=True)
    print("  Class pixel counts:")
    for u, c in zip(unique, counts):
        print(f"    {u}: {c}")


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    print(
        "predict.py requires a feature_array/valid_mask/transform/crs produced by "
        "preprocess.assemble_feature_stack() from a real Sentinel-2 acquisition — "
        "run the full pipeline (run_pipeline.py) rather than this module standalone, "
        "since it has no independent data source of its own."
    )
