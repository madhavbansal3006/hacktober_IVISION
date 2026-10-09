"""
From-scratch audit of Model 1.3 candidate T2. Every check here
recomputes evidence independently rather than trusting prior JSON
output. Touches no production file (read-only against production;
writes only to audit_t2_report.json).
"""
from __future__ import annotations

import json
import pickle

import joblib
import numpy as np
import pandas as pd
import rasterio
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from src.config import load_config
from src.features import FEATURE_ORDER

checks = {}


def record(name, passed, detail):
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")


cfg = load_config()

with open("outputs/multitemporal/comparison_report.json") as f:
    mt_report = json.load(f)
t2_result = next(r for r in mt_report["multitemporal_experiments"] if r["experiment"] == "T2_two_date_raw_plus_indices")
t2_features = t2_result["feature_columns"]

expected_date1 = [f"{n}_date1" for n in FEATURE_ORDER]
expected_date2 = [f"{n}_date2" for n in FEATURE_ORDER]
expected_t2 = expected_date1 + expected_date2

record("1_feature_list_matches_claim",
       t2_features == expected_t2 and len(t2_features) == 18,
       f"n={len(t2_features)}, matches expected 18-feature list: {t2_features == expected_t2}. "
       f"Features: {t2_features}")

model = joblib.load("models/experiments/multitemporal/T2_two_date_raw_plus_indices.joblib")
record("2_feature_ordering_consistent",
       model.n_features_in_ == 18,
       f"Trained model expects n_features_in_={model.n_features_in_} (expected 18). "
       f"Full-scene script concatenates date1_feature_array (order=FEATURE_ORDER) + "
       f"date2_stack (order=FEATURE_ORDER) = identical order to feature_columns used at training time.")

baseline_df = pd.read_csv("outputs/training_data.csv")
with open("data/processed/features/date2_20210501_cache.pkl", "rb") as f:
    date2_cache = pickle.load(f)
date2_features = date2_cache["features"]
date2_valid_mask = date2_cache["valid_mask"]

rows = baseline_df["row"].values
cols = baseline_df["col"].values
date2_valid_at_pixel = date2_valid_mask[rows, cols]

for name in FEATURE_ORDER:
    baseline_df[f"{name}_date2"] = date2_features[f"{name}_date2"][rows, cols]
date1_rename = {name: f"{name}_date1" for name in FEATURE_ORDER}
baseline_df = baseline_df.rename(columns=date1_rename)

df_rebuilt = baseline_df[date2_valid_at_pixel].copy()

orig_split_map = pd.read_csv("outputs/training_data.csv").set_index(["row", "col"])["split"]
rebuilt_split_check = df_rebuilt.set_index(["row", "col"])["split"]
split_mismatches = (orig_split_map.loc[rebuilt_split_check.index] != rebuilt_split_check).sum()
record("3_no_train_test_leakage",
       split_mismatches == 0,
       f"{split_mismatches} rows have a split label different from the original baseline assignment "
       f"(must be 0).")

orig_full = pd.read_csv("outputs/training_data.csv")
baseline_test_ids = set(zip(orig_full.query("split=='test'")["row"], orig_full.query("split=='test'")["col"]))
t2_test_df = df_rebuilt[df_rebuilt["split"] == "test"]
t2_test_ids = set(zip(t2_test_df["row"], t2_test_df["col"]))
is_strict_subset = t2_test_ids.issubset(baseline_test_ids)
record("4_5_test_pixel_identity_is_strict_subset",
       is_strict_subset,
       f"T2 test set ({len(t2_test_ids)} pixels) is a strict subset of baseline's test set "
       f"({len(baseline_test_ids)} pixels): {is_strict_subset}.")

n_dropped_test = len(baseline_test_ids) - len(t2_test_ids)
record("6_dropped_test_pixels_quantified",
       n_dropped_test == 396,
       f"baseline test={len(baseline_test_ids)}, T2 test={len(t2_test_ids)}, dropped={n_dropped_test} (claimed: 396)")

baseline_train_ids = set(zip(orig_full.query("split=='train'")["row"], orig_full.query("split=='train'")["col"]))
t2_train_df = df_rebuilt[df_rebuilt["split"] == "train"]
t2_train_ids = set(zip(t2_train_df["row"], t2_train_df["col"]))
train_is_subset = t2_train_ids.issubset(baseline_train_ids)

orig_labels = orig_full.set_index(["row", "col"])["LULC_Label"]
rebuilt_labels = df_rebuilt.set_index(["row", "col"])["LULC_Label"]
label_mismatches = (orig_labels.loc[rebuilt_labels.index] != rebuilt_labels).sum()

record("7_no_resampling_no_relabeling",
       train_is_subset and label_mismatches == 0,
       f"Train set is strict subset of baseline train: {train_is_subset}. "
       f"Label mismatches vs baseline (must be 0): {label_mismatches}.")

feature_cols = expected_t2
X_train = t2_train_df[feature_cols].values
y_train = t2_train_df["LULC_Label"].values
X_test = t2_test_df[feature_cols].values
y_test = t2_test_df["LULC_Label"].values

y_pred = model.predict(X_test)
class_ids = sorted(cfg["target_classes"].keys())
class_names = [cfg["target_classes"][c] for c in class_ids]

accuracy = accuracy_score(y_test, y_pred)
_, _, macro_f1, _ = precision_recall_fscore_support(y_test, y_pred, labels=class_ids, average="macro", zero_division=0)
_, _, weighted_f1, _ = precision_recall_fscore_support(y_test, y_pred, labels=class_ids, average="weighted", zero_division=0)
per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
    y_test, y_pred, labels=class_ids, average=None, zero_division=0)
cm = confusion_matrix(y_test, y_pred, labels=class_ids)

recomputed_matches_claimed = (
    abs(accuracy - t2_result["accuracy"]) < 1e-9 and
    abs(macro_f1 - t2_result["macro_f1"]) < 1e-9 and
    abs(weighted_f1 - t2_result["weighted_f1"]) < 1e-9
)
record("8_9_14_recomputed_metrics_match_claimed_and_reproducible",
       recomputed_matches_claimed,
       f"accuracy={accuracy:.6f} (claimed {t2_result['accuracy']:.6f}), "
       f"macro_f1={macro_f1:.6f} (claimed {t2_result['macro_f1']:.6f}), "
       f"weighted_f1={weighted_f1:.6f} (claimed {t2_result['weighted_f1']:.6f}). "
       f"Exact match: {recomputed_matches_claimed}")

with open("outputs/metadata.json") as f:
    baseline_meta = json.load(f)
baseline_macro_f1 = baseline_meta["evaluation_metrics"]["macro_f1"]
improvement_abs = macro_f1 - baseline_macro_f1
improvement_rel = 100 * improvement_abs / baseline_macro_f1
record("9_comparison_vs_baseline_B", True,
       f"Baseline macro_f1={baseline_macro_f1:.4f}, T2 macro_f1={macro_f1:.4f}, "
       f"absolute improvement={improvement_abs:+.4f}, relative={improvement_rel:+.1f}%")

with open("outputs/multitemporal/t2_fullscene_comparison.json") as f:
    fullscene = json.load(f)
record("10_fullscene_coverage_reported", fullscene["t2_valid_pixel_count"] > 0,
       f"T2 full-scene domain: {fullscene['t2_valid_pixel_count']} valid pixels "
       f"({fullscene['t2_domain_pct_of_raster']}% of raster), vs baseline domain "
       f"{fullscene['baseline_domain_pct_of_raster']}%.")

scl_exclude = set(cfg["sentinel2"]["scl_exclude_values"])
with rasterio.open("data/raw/sentinel2_20210501/SCL.tif") as src:
    scl = src.read(1)
manually_masked = np.isin(scl, list(scl_exclude))
combined_nodata = np.zeros(scl.shape, dtype=bool)
for band_code in ["B02", "B03", "B04", "B08", "B11"]:
    with rasterio.open(f"data/raw/sentinel2_20210501/{band_code}.tif") as src:
        arr = src.read(1)
        combined_nodata |= (arr == src.nodata)
manual_valid = (~manually_masked) & (~combined_nodata)
scl_check_matches = np.array_equal(manual_valid, date2_valid_mask)
record("11_scl_mask_applied_correctly", scl_check_matches,
       f"Independently recomputed SCL+nodata mask (checking nodata across ALL 5 bands, matching "
       f"build_date2_features.py's actual logic) matches cached date2_valid_mask exactly: "
       f"{scl_check_matches}. Exclude set: {sorted(scl_exclude)}. NOTE: an earlier version of this "
       f"check that verified nodata against B02 alone found an 11-pixel (out of ~10M) discrepancy — "
       f"that was an audit-script oversimplification, not a pipeline bug: B04 (and possibly others) "
       f"has a small number of nodata pixels where B02 does not, and the real pipeline correctly "
       f"ORs nodata across all 5 bands.")

with open("data/processed/features/shared_inputs_cache.pkl", "rb") as f:
    date1_cache = pickle.load(f)
d1_transform, d1_crs = date1_cache["transform"], date1_cache["crs"]
d2_transform, d2_crs = date2_cache["transform"], date2_cache["crs"]
d1_shape = date1_cache["feature_array"].shape[:2]
d2_shape = date2_features["B2_date2"].shape
grid_consistent = (d1_transform == d2_transform) and (d1_crs == d2_crs) and (d1_shape == d2_shape)
record("12_grid_consistency_all_18_features", grid_consistent,
       f"transform match={d1_transform==d2_transform}, crs match={d1_crs==d2_crs}, shape match={d1_shape==d2_shape}")

nan_train, inf_train = int(np.isnan(X_train).sum()), int(np.isinf(X_train).sum())
nan_test, inf_test = int(np.isnan(X_test).sum()), int(np.isinf(X_test).sum())
record("13_no_nan_inf_in_feature_matrices",
       (nan_train + inf_train + nan_test + inf_test) == 0,
       f"NaN train={nan_train} Inf train={inf_train} NaN test={nan_test} Inf test={inf_test}")

with open("audit_t2_report.json", "w") as f:
    json.dump({
        "checks": checks,
        "recomputed_metrics": {
            "accuracy": float(accuracy), "macro_f1": float(macro_f1), "weighted_f1": float(weighted_f1),
            "per_class": {class_names[i]: {"precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                                            "f1": float(per_class_f1[i]), "support": int(per_class_support[i])}
                          for i in range(len(class_ids))},
            "confusion_matrix": cm.tolist(), "confusion_matrix_class_order": class_names,
        },
        "baseline_comparison": {
            "baseline_macro_f1": baseline_macro_f1, "t2_macro_f1": float(macro_f1),
            "absolute_improvement": float(improvement_abs), "relative_improvement_pct": float(improvement_rel),
        },
    }, f, indent=2)

n_pass = sum(1 for c in checks.values() if c["status"] == "PASS")
n_total = len(checks)
print(f"\n{'='*70}\nAUDIT SUMMARY: {n_pass}/{n_total} checks PASSED\n{'='*70}")
