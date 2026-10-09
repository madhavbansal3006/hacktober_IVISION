"""
Model 1.3 — multi-temporal experiments (T0/T1/T2/T3) testing whether
adding a second Sentinel-2 date (2021-05-01) improves the diagnosed
Agriculture<->Built-up and Water<->Barren confusion.

Design constraints, enforced directly in code:
  - Uses the EXISTING WorldCover-derived labels and the EXISTING
    train/test split from outputs/training_data.csv — no new sampling,
    no new labels. Row/col identity is preserved so every experiment
    evaluates on (a subset of) the exact same pixels as baseline.
  - Date2 features are looked up at those exact (row, col) locations.
    Pixels invalid under date2's SCL+nodata mask cannot be evaluated
    with date2 features and are dropped from T1/T2/T3 — exact counts
    reported per class per split, not hidden.
  - No pixel ever moves from test to train or vice versa.
  - Does not touch any protected production file.
"""
from __future__ import annotations

import json
import os
import pickle
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from src.config import load_config, ensure_dirs
from src.features import FEATURE_ORDER

DATE2_CACHE = "data/processed/features/date2_20210501_cache.pkl"
SHARED_CACHE = "data/processed/features/shared_inputs_cache.pkl"
MODEL_OUT_DIR = "models/experiments/multitemporal"
OUT_DIR = "outputs/multitemporal"


def main():
    cfg = load_config()
    ensure_dirs(cfg)
    os.makedirs(MODEL_OUT_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    baseline_df = pd.read_csv("outputs/training_data.csv")
    print(f"Loaded baseline training_data.csv: {len(baseline_df)} rows "
          f"({(baseline_df['split']=='train').sum()} train, {(baseline_df['split']=='test').sum()} test)")

    with open(DATE2_CACHE, "rb") as f:
        date2_cache = pickle.load(f)
    date2_features = date2_cache["features"]   # {name_date2: 2D array}
    date2_valid_mask = date2_cache["valid_mask"]

    # --- Look up date2 feature values + validity at each existing (row,col) ---
    rows = baseline_df["row"].values
    cols = baseline_df["col"].values
    date2_valid_at_pixel = date2_valid_mask[rows, cols]

    for name in FEATURE_ORDER:
        baseline_df[f"{name}_date2"] = date2_features[f"{name}_date2"][rows, cols]

    n_before = len(baseline_df)
    n_dropped = int((~date2_valid_at_pixel).sum())
    print(f"\nPixels invalid under date2's SCL+nodata mask: {n_dropped} / {n_before} "
          f"({100*n_dropped/n_before:.2f}%)")

    # Report exact drop counts per class per split before actually dropping
    drop_report = baseline_df[~date2_valid_at_pixel].groupby(["LULC_Label", "split"]).size()
    print("Dropped rows by class/split:")
    print(drop_report)

    df = baseline_df[date2_valid_at_pixel].copy()
    print(f"\nRemaining after date2-validity filter: {len(df)} rows "
          f"({(df['split']=='train').sum()} train, {(df['split']=='test').sum()} test)")
    print("Remaining class counts by split:")
    print(df.groupby(["split", "LULC_Label"]).size())

    # Rename date1 columns for clarity (existing B2..BSI columns = date1)
    date1_rename = {name: f"{name}_date1" for name in FEATURE_ORDER}
    df = df.rename(columns=date1_rename)
    baseline_df_t0 = baseline_df.rename(columns=date1_rename)  # T0 uses ALL baseline rows, unfiltered

    # --- Temporal difference/statistical features (T3 only) ---
    df["NDVI_difference"] = df["NDVI_date2"] - df["NDVI_date1"]
    df["NDVI_absolute_difference"] = df["NDVI_difference"].abs()
    df["NDVI_mean"] = (df["NDVI_date1"] + df["NDVI_date2"]) / 2
    df["NDVI_std"] = df[["NDVI_date1", "NDVI_date2"]].std(axis=1)
    df["NDWI_difference"] = df["NDWI_date2"] - df["NDWI_date1"]
    df["NDBI_difference"] = df["NDBI_date2"] - df["NDBI_date1"]
    df["BSI_difference"] = df["BSI_date2"] - df["BSI_date1"]

    feature_sets = {
        "T0_baseline_reproduction": [f"{n}_date1" for n in FEATURE_ORDER],  # 9 features, uses baseline_df_t0
        "T1_two_date_raw_bands": [f"{b}_date1" for b in ["B2", "B3", "B4", "B8", "B11"]] +
                                   [f"{b}_date2" for b in ["B2", "B3", "B4", "B8", "B11"]],  # 10
        "T2_two_date_raw_plus_indices": [f"{n}_date1" for n in FEATURE_ORDER] +
                                          [f"{n}_date2" for n in FEATURE_ORDER],  # 18
        "T3_plus_temporal_diff_stats": [f"{n}_date1" for n in FEATURE_ORDER] +
                                         [f"{n}_date2" for n in FEATURE_ORDER] +
                                         ["NDVI_difference", "NDVI_absolute_difference", "NDVI_mean",
                                          "NDVI_std", "NDWI_difference", "NDBI_difference", "BSI_difference"],  # 25
    }

    class_ids = sorted(cfg["target_classes"].keys())
    class_names = [cfg["target_classes"][c] for c in class_ids]
    ag_idx, bu_idx = class_names.index("Agriculture"), class_names.index("Built-up")
    wa_idx, ba_idx = class_names.index("Water"), class_names.index("Barren")

    all_results = []
    for exp_name, feat_cols in feature_sets.items():
        t0 = time.time()
        print(f"\n{'='*70}\n{exp_name}  ({len(feat_cols)} features)\n{'='*70}")

        use_df = baseline_df_t0 if exp_name.startswith("T0") else df
        train_df = use_df[use_df["split"] == "train"]
        test_df = use_df[use_df["split"] == "test"]
        X_train, y_train = train_df[feat_cols].values, train_df["LULC_Label"].values
        X_test, y_test = test_df[feat_cols].values, test_df["LULC_Label"].values

        model = RandomForestClassifier(
            n_estimators=cfg["random_forest"]["n_estimators"], random_state=42,
            class_weight=None, n_jobs=cfg["random_forest"]["n_jobs"],
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average="macro", zero_division=0)
        weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average="weighted", zero_division=0)
        per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average=None, zero_division=0)
        cm = confusion_matrix(y_test, y_pred, labels=class_ids)

        ag_to_bu, bu_to_ag = int(cm[ag_idx, bu_idx]), int(cm[bu_idx, ag_idx])
        wa_to_ba, ba_to_wa = int(cm[wa_idx, ba_idx]), int(cm[ba_idx, wa_idx])

        print(f"  n_train={len(X_train)} n_test={len(X_test)} n_features={len(feat_cols)}")
        print(f"  accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} weighted_f1={weighted_f1:.4f}")
        print(f"  Agriculture->Built-up={ag_to_bu} Built-up->Agriculture={bu_to_ag} "
              f"(total cross-confusion={ag_to_bu+bu_to_ag})")
        print(f"  Water->Barren={wa_to_ba} Barren->Water={ba_to_wa} "
              f"(total cross-confusion={wa_to_ba+ba_to_wa})")

        result = {
            "experiment": exp_name, "n_features": len(feat_cols), "feature_columns": feat_cols,
            "n_train": int(len(X_train)), "n_test": int(len(X_test)),
            "accuracy": float(accuracy), "macro_f1": float(macro_f1), "weighted_f1": float(weighted_f1),
            "per_class": {
                class_names[i]: {"precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                                  "f1": float(per_class_f1[i]), "support": int(per_class_support[i])}
                for i in range(len(class_ids))
            },
            "confusion_matrix": cm.tolist(), "confusion_matrix_class_order": class_names,
            "agriculture_to_builtup": ag_to_bu, "builtup_to_agriculture": bu_to_ag,
            "agriculture_builtup_total_cross_confusion": ag_to_bu + bu_to_ag,
            "water_to_barren": wa_to_ba, "barren_to_water": ba_to_wa,
            "water_barren_total_cross_confusion": wa_to_ba + ba_to_wa,
            "elapsed_seconds": round(time.time() - t0, 1),
        }
        all_results.append(result)
        joblib.dump(model, f"{MODEL_OUT_DIR}/{exp_name}.joblib")

    with open("outputs/metadata.json") as f:
        baseline_meta = json.load(f)
    baseline_summary = {
        "accuracy": baseline_meta["evaluation_metrics"]["accuracy"],
        "macro_f1": baseline_meta["evaluation_metrics"]["macro_f1"],
        "weighted_f1": baseline_meta["evaluation_metrics"]["weighted_f1"],
        "per_class": baseline_meta["evaluation_metrics"]["per_class"],
    }

    comparison = {
        "baseline_experiment_B": baseline_summary,
        "date2_drop_info": {
            "n_baseline_rows": n_before, "n_dropped_date2_invalid": n_dropped,
            "pct_dropped": round(100 * n_dropped / n_before, 2),
        },
        "multitemporal_experiments": all_results,
    }
    with open(f"{OUT_DIR}/comparison_report.json", "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nWrote {OUT_DIR}/comparison_report.json")


if __name__ == "__main__":
    main()
