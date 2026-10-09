"""
Full-scene prediction for T2 (best multi-temporal candidate), for
comparison against production Model 1's full-scene class proportions.

IMPORTANT DOMAIN CAVEAT: T2 requires BOTH dates' features to be valid at
a pixel. Its full-scene prediction domain is therefore the INTERSECTION
of date1's valid mask (nodata only) and date2's valid mask (nodata + SCL
cloud/shadow exclusion) — necessarily smaller than production Model 1's
single-date domain. Class percentages are reported within each model's
own valid domain; they are not being silently compared as if computed
over identical pixel sets.
"""
from __future__ import annotations

import json
import pickle
import time

import joblib
import numpy as np

from src.config import load_config
from src.features import FEATURE_ORDER

SHARED_CACHE = "data/processed/features/shared_inputs_cache.pkl"
DATE2_CACHE = "data/processed/features/date2_20210501_cache.pkl"
MODEL_PATH = "models/experiments/multitemporal/T2_two_date_raw_plus_indices.joblib"


def main():
    cfg = load_config()
    t0 = time.time()

    with open(SHARED_CACHE, "rb") as f:
        date1_cache = pickle.load(f)
    date1_feature_array = date1_cache["feature_array"]   # (rows, cols, 9), order = FEATURE_ORDER
    date1_valid_mask = date1_cache["valid_mask"]
    transform = date1_cache["transform"]
    crs = date1_cache["crs"]

    with open(DATE2_CACHE, "rb") as f:
        date2_cache = pickle.load(f)
    date2_features = date2_cache["features"]
    date2_valid_mask = date2_cache["valid_mask"]

    combined_valid = date1_valid_mask & date2_valid_mask
    print(f"Date1 valid: {100*date1_valid_mask.sum()/date1_valid_mask.size:.2f}%")
    print(f"Date2 valid: {100*date2_valid_mask.sum()/date2_valid_mask.size:.2f}%")
    print(f"Combined (intersection) valid: {100*combined_valid.sum()/combined_valid.size:.2f}%")

    date2_stack = np.stack([date2_features[f"{n}_date2"] for n in FEATURE_ORDER], axis=-1)
    full_feature_array = np.concatenate([date1_feature_array, date2_stack], axis=-1)  # 18 features

    model = joblib.load(MODEL_PATH)
    print(f"Loaded T2 model, n_features_in_={model.n_features_in_}")

    rows, cols, n_feat = full_feature_array.shape
    flat_features = full_feature_array.reshape(-1, n_feat)
    flat_valid = combined_valid.reshape(-1)
    valid_idx = np.where(flat_valid)[0]

    class_ids = sorted(cfg["target_classes"].keys())
    full_scene_counts = {int(c): 0 for c in class_ids}
    chunk = 500_000
    for start in range(0, len(valid_idx), chunk):
        idx_chunk = valid_idx[start:start + chunk]
        pred_chunk = model.predict(flat_features[idx_chunk])
        for c in class_ids:
            full_scene_counts[c] += int((pred_chunk == c).sum())
    full_scene_total = sum(full_scene_counts.values())
    full_scene_pct = {cfg["target_classes"][c]: round(100 * full_scene_counts[c] / full_scene_total, 2)
                       for c in class_ids}
    print(f"T2 full-scene predicted proportions (n={full_scene_total} valid pixels, "
          f"intersection domain): {full_scene_pct}")

    with open("outputs/metadata.json") as f:
        baseline_meta = json.load(f)
    baseline_pct = baseline_meta["full_scene_predicted_class_percent"]
    baseline_domain_n = sum(baseline_meta["evaluation_metrics"]["per_class"][c]["support"] for c in
                             baseline_meta["evaluation_metrics"]["per_class"])  # not full domain, just for reference

    print(f"\nBaseline (production) full-scene proportions (single-date, larger domain): {baseline_pct}")
    print("\n*** DOMAIN NOTE: T2's domain is the date1+date2 intersection "
          f"({100*combined_valid.sum()/combined_valid.size:.2f}% of pixels), smaller than "
          f"production's single-date domain ({100*date1_valid_mask.sum()/date1_valid_mask.size:.2f}% of pixels). "
          "These percentages are each computed within their own model's valid domain, not a shared pixel set. ***")

    result = {
        "t2_full_scene_predicted_percent": full_scene_pct,
        "t2_valid_pixel_count": int(full_scene_total),
        "t2_domain_pct_of_raster": round(100 * combined_valid.sum() / combined_valid.size, 2),
        "baseline_full_scene_predicted_percent": baseline_pct,
        "baseline_domain_pct_of_raster": round(100 * date1_valid_mask.sum() / date1_valid_mask.size, 2),
        "domain_note": (
            "T2 requires both dates' features to be valid at each pixel, so its full-scene domain "
            "(date1 AND date2 valid) is smaller than production Model 1's single-date domain "
            "(date1 valid only). Percentages are computed within each model's own domain and are "
            "NOT directly comparable pixel-for-pixel."
        ),
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open("outputs/multitemporal/t2_fullscene_comparison.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote outputs/multitemporal/t2_fullscene_comparison.json")


if __name__ == "__main__":
    main()
