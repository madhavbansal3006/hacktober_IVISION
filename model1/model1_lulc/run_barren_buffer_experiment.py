"""
Controlled Barren-label spatial filtering experiment (Model 1.2 candidate
search). Tests 5 exclusion buffers (20/30/50/75/100m) removing Barren
TRAINING candidates near Water, motivated by the diagnostic finding that
49.4% of Barren training pixels are within 100m of Water and that
misclassified Water<->Barren pixels sit at median distances of 36-52m.

Design, chosen specifically to satisfy "test/validation labels must NOT be
filtered":
  - Starts from the EXACT baseline outputs/training_data.csv (Experiment
    B's real saved sample + real spatial-block split) — not resampled,
    not regenerated.
  - The buffer filter is applied ONLY to rows where split=='train' AND
    LULC_Label==5 (Barren). The test split is byte-identical to Experiment
    B's test split in every variant.
  - All other classes' train rows are untouched in every variant.
  - No oversampling/duplication to compensate for removed Barren rows —
    if filtering leaves fewer Barren training pixels, that's what gets
    used, and the actual count is reported.
  - Water reference set for distance = the 3000 Water rows already in
    training_data.csv (same reference used in the prior diagnostic, for
    direct comparability with the reported 36m/52m/103m/120m figures).

Does NOT touch models/lulc_random_forest.joblib or any existing Experiment
B output. All artifacts go to models/experiments/barren_buffer/ and
outputs/barren_buffer/.
"""
from __future__ import annotations

import json
import os
import pickle
import time

import joblib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from src.config import load_config, ensure_dirs

CACHE_PATH = "data/processed/features/shared_inputs_cache.pkl"
MODEL_OUT_DIR = "models/experiments/barren_buffer"
OUT_DIR = "outputs/barren_buffer"
BUFFERS = [20, 30, 50, 75, 100]

import sys
if len(sys.argv) > 1:
    BUFFERS = [int(x) for x in sys.argv[1:]]



def main():
    cfg = load_config()
    ensure_dirs(cfg)
    os.makedirs(MODEL_OUT_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    baseline_df = pd.read_csv("outputs/training_data.csv")
    with open("outputs/metadata.json") as f:
        baseline_meta = json.load(f)
    baseline = {
        "accuracy": baseline_meta["evaluation_metrics"]["accuracy"],
        "macro_f1": baseline_meta["evaluation_metrics"]["macro_f1"],
        "weighted_f1": baseline_meta["evaluation_metrics"]["weighted_f1"],
        "per_class": baseline_meta["evaluation_metrics"]["per_class"],
        "full_scene_predicted_percent": baseline_meta["full_scene_predicted_class_percent"],
    }
    print("Baseline (Experiment B, from outputs/metadata.json):")
    print(f"  accuracy={baseline['accuracy']:.4f} macro_f1={baseline['macro_f1']:.4f} "
          f"weighted_f1={baseline['weighted_f1']:.4f}")

    water_xy = baseline_df[baseline_df["LULC_Label"] == 3][["x", "y"]].values
    water_tree = cKDTree(water_xy)
    print(f"Water reference set: {len(water_xy)} pixels (same set used in the prior diagnostic)")

    barren_train_mask = (baseline_df["LULC_Label"] == 5) & (baseline_df["split"] == "train")
    n_barren_train_before = int(barren_train_mask.sum())
    barren_train_idx = baseline_df[barren_train_mask].index
    barren_train_xy = baseline_df.loc[barren_train_idx, ["x", "y"]].values
    dist_to_water, _ = water_tree.query(barren_train_xy, k=1)
    print(f"Barren TRAINING candidates before filtering: {n_barren_train_before} "
          f"(756 Barren test rows are untouched in every variant)")

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    feature_array = cache["feature_array"]
    valid_mask = cache["valid_mask"]
    transform = cache["transform"]

    feature_cols = cfg["features"]["names"]
    class_ids = sorted(cfg["target_classes"].keys())
    class_names = [cfg["target_classes"][c] for c in class_ids]

    test_df = baseline_df[baseline_df["split"] == "test"]
    X_test = test_df[feature_cols].values
    y_test = test_df["LULC_Label"].values

    all_results = []
    for buffer_m in BUFFERS:
        t0 = time.time()
        print(f"\n{'='*70}\nBUFFER = {buffer_m}m\n{'='*70}")

        keep_mask_within_barren_train = dist_to_water >= buffer_m
        n_remaining = int(keep_mask_within_barren_train.sum())
        kept_idx = barren_train_idx[keep_mask_within_barren_train]
        print(f"  Barren training candidates remaining after {buffer_m}m exclusion: {n_remaining} "
              f"(removed {n_barren_train_before - n_remaining})")

        if n_remaining == 0:
            print(f"  WARNING: buffer {buffer_m}m removes ALL Barren training candidates. Skipping — "
                  f"cannot train without fabricating or duplicating samples.")
            all_results.append({"buffer_m": buffer_m, "skipped": True,
                                 "n_barren_before": n_barren_train_before, "n_barren_after": 0})
            continue

        other_train_df = baseline_df[(baseline_df["split"] == "train") & (baseline_df["LULC_Label"] != 5)]
        barren_train_filtered_df = baseline_df.loc[kept_idx]
        train_df = pd.concat([other_train_df, barren_train_filtered_df], ignore_index=True)

        n_actually_sampled = len(barren_train_filtered_df)
        print(f"  Number actually used for Barren training: {n_actually_sampled} (no oversampling/duplication)")
        print(f"  Total training set size: {len(train_df)} (baseline was "
              f"{(baseline_df['split']=='train').sum()})")

        X_train = train_df[feature_cols].values
        y_train = train_df["LULC_Label"].values

        model = RandomForestClassifier(
            n_estimators=cfg["random_forest"]["n_estimators"], random_state=42,
            class_weight=None, n_jobs=cfg["random_forest"]["n_jobs"],
        )
        model.fit(X_train, y_train)
        print(f"  Trained in {time.time()-t0:.1f}s")

        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average="macro", zero_division=0)
        weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average="weighted", zero_division=0)
        per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
            y_test, y_pred, labels=class_ids, average=None, zero_division=0)
        cm = confusion_matrix(y_test, y_pred, labels=class_ids)
        print(f"  accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} weighted_f1={weighted_f1:.4f}")

        water_idx = class_names.index("Water")
        barren_idx = class_names.index("Barren")
        water_to_barren = int(cm[water_idx, barren_idx])
        barren_to_water = int(cm[barren_idx, water_idx])
        print(f"  Water->Barren errors: {water_to_barren} (baseline: 200)")
        print(f"  Barren->Water errors: {barren_to_water} (baseline: 69)")

        # Full-scene prediction (chunked)
        rows, cols, n_feat = feature_array.shape
        flat_features = feature_array.reshape(-1, n_feat)
        flat_valid = valid_mask.reshape(-1)
        valid_idx = np.where(flat_valid)[0]
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
        print(f"  Full-scene %: {full_scene_pct}")

        result = {
            "buffer_m": buffer_m, "skipped": False,
            "n_barren_train_before": n_barren_train_before,
            "n_barren_train_after_filter": n_remaining,
            "n_barren_actually_used": n_actually_sampled,
            "accuracy": float(accuracy), "macro_f1": float(macro_f1), "weighted_f1": float(weighted_f1),
            "per_class": {
                class_names[i]: {"precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                                  "f1": float(per_class_f1[i]), "support": int(per_class_support[i])}
                for i in range(len(class_ids))
            },
            "confusion_matrix": cm.tolist(), "confusion_matrix_class_order": class_names,
            "full_scene_predicted_percent": full_scene_pct,
            "water_to_barren_errors": water_to_barren, "barren_to_water_errors": barren_to_water,
            "elapsed_seconds": round(time.time() - t0, 1),
        }
        all_results.append(result)

        joblib.dump(model, f"{MODEL_OUT_DIR}/buffer_{buffer_m}m.joblib")
        train_df.to_csv(f"{OUT_DIR}/training_data_buffer_{buffer_m}m.csv", index=False)

    if os.path.exists(f"{OUT_DIR}/comparison_report.json"):
        try:
            with open(f"{OUT_DIR}/comparison_report.json") as f:
                existing = json.load(f)
            existing_results = existing.get("buffer_experiments", [])
            current_buffers = {r["buffer_m"] for r in all_results}
            merged = [r for r in existing_results if r["buffer_m"] not in current_buffers] + all_results
            merged.sort(key=lambda r: r["buffer_m"])
            all_results = merged
        except Exception:
            pass
    with open(f"{OUT_DIR}/comparison_report.json", "w") as f:
        json.dump({"baseline_experiment_B": baseline, "buffer_experiments": all_results}, f, indent=2)

    print("\n" + "=" * 90)
    print("COMPARISON: Baseline vs Barren-buffer variants")
    print("=" * 90)
    header = f"{'Variant':16s} {'BarrenN':>8s} {'Acc':>7s} {'MacroF1':>8s} {'WtF1':>7s} {'BarrenF1':>9s} {'WaterF1':>8s} {'W->B':>5s} {'B->W':>5s}"
    print(header)
    print(f"{'Baseline B':16s} {'3000':>8s} {baseline['accuracy']:7.4f} {baseline['macro_f1']:8.4f} "
          f"{baseline['weighted_f1']:7.4f} {baseline['per_class']['Barren']['f1']:9.4f} "
          f"{baseline['per_class']['Water']['f1']:8.4f} {'200':>5s} {'69':>5s}")
    for r in all_results:
        if r.get("skipped"):
            print(f"{str(r['buffer_m'])+'m':16s} {'SKIPPED (0 remaining)':>8s}")
            continue
        print(f"{str(r['buffer_m'])+'m':16s} {r['n_barren_actually_used']:>8d} {r['accuracy']:7.4f} "
              f"{r['macro_f1']:8.4f} {r['weighted_f1']:7.4f} {r['per_class']['Barren']['f1']:9.4f} "
              f"{r['per_class']['Water']['f1']:8.4f} {r['water_to_barren_errors']:>5d} {r['barren_to_water_errors']:>5d}")

    print(f"\nWrote {OUT_DIR}/comparison_report.json")


if __name__ == "__main__":
    main()
