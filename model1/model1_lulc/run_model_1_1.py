"""
Model 1.1 — controlled experiment testing a hybrid sqrt-proportional,
block-capped sampling strategy against the production Experiment B
baseline. Does NOT modify any existing production file:
  - models/lulc_random_forest.joblib is untouched
  - outputs/*.tif, outputs/*.csv, outputs/metadata.json etc. are untouched
  - Experiments A/B/C are not rerun (uses the same cached shared inputs)

All Model 1.1 artifacts go to a separate namespace:
  - models/lulc_random_forest_v1_1.joblib
  - outputs/model1_v1_1/

Baseline numbers used for comparison are read directly from the existing
outputs/metadata.json / outputs/experiment_comparison.json — not
retyped from memory.
"""
from __future__ import annotations

import json
import os
import pickle
import time

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from src.config import load_config, ensure_dirs
from src.sampling import hybrid_sqrt_sample, finalize_columns, spatial_block_split
from src.predict import predict_full_raster, write_prediction_geotiff, write_confidence_geotiff, summarize_confidence

CACHE_PATH = "data/processed/features/shared_inputs_cache.pkl"
OUT_DIR = "outputs/model1_v1_1"
MODEL_PATH = "models/lulc_random_forest_v1_1.joblib"


def main():
    cfg = load_config()
    ensure_dirs(cfg)
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    # --- Load baseline numbers from disk, not memory ---
    with open("outputs/metadata.json") as f:
        baseline_meta = json.load(f)
    baseline = {
        "accuracy": baseline_meta["evaluation_metrics"]["accuracy"],
        "macro_f1": baseline_meta["evaluation_metrics"]["macro_f1"],
        "weighted_f1": baseline_meta["evaluation_metrics"]["weighted_f1"],
        "per_class": baseline_meta["evaluation_metrics"]["per_class"],
        "full_scene_predicted_percent": baseline_meta["full_scene_predicted_class_percent"],
    }
    print("Loaded baseline (Experiment B) from outputs/metadata.json:")
    print(f"  accuracy={baseline['accuracy']:.4f} macro_f1={baseline['macro_f1']:.4f} "
          f"weighted_f1={baseline['weighted_f1']:.4f}")

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    feature_array = cache["feature_array"]
    valid_mask = cache["valid_mask"]
    aligned_labels = cache["aligned_labels"]
    transform = cache["transform"]
    crs = cache["crs"]

    # --- Step 2: hybrid sampling ---
    print("\nGenerating Model 1.1 hybrid sqrt-proportional, block-capped samples...")
    df = hybrid_sqrt_sample(
        feature_array, aligned_labels, transform, cfg["target_classes"],
        total_budget=18000, min_floor=300, block_size_m=cfg["sampling"]["spatial_block_size_m"],
        block_spread_factor=3.0, random_state=42,
    )
    df = finalize_columns(df, cfg["features"]["names"])

    # --- Step 3: keep spatial block split ---
    df = spatial_block_split(df, cfg["sampling"]["spatial_block_size_m"],
                              cfg["sampling"]["test_block_fraction"], random_state=42)
    df.to_csv(f"{OUT_DIR}/training_data_v1_1.csv", index=False)

    # --- Step 4: train ---
    feature_cols = cfg["features"]["names"]
    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]
    X_train, y_train = train_df[feature_cols].values, train_df["LULC_Label"].values
    X_test, y_test = test_df[feature_cols].values, test_df["LULC_Label"].values

    model = RandomForestClassifier(
        n_estimators=cfg["random_forest"]["n_estimators"], random_state=42,
        class_weight=None, n_jobs=cfg["random_forest"]["n_jobs"],
    )
    print(f"\nTraining Model 1.1 on {len(X_train)} samples ({len(X_test)} test)...")
    model.fit(X_train, y_train)
    print(f"  Training done at {time.time()-t0:.1f}s")

    # --- Step 5: evaluate ---
    y_pred = model.predict(X_test)
    class_ids = sorted(cfg["target_classes"].keys())
    class_names = [cfg["target_classes"][c] for c in class_ids]

    accuracy = accuracy_score(y_test, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="macro", zero_division=0)
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="weighted", zero_division=0)
    per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average=None, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=class_ids)
    print(f"  accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} weighted_f1={weighted_f1:.4f}")

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
    print(f"  Full-scene predicted proportions: {full_scene_pct}")
    print(f"  Full-scene prediction done at {time.time()-t0:.1f}s")

    v1_1_result = {
        "model": "Model 1.1 (hybrid sqrt-proportional, block-capped sampling)",
        "n_train_samples": int(len(X_train)), "n_test_samples": int(len(X_test)),
        "sample_counts_by_class": {class_names[i]: int((df["LULC_Label"] == class_ids[i]).sum())
                                    for i in range(len(class_ids))},
        "accuracy": float(accuracy), "macro_f1": float(macro_f1), "weighted_f1": float(weighted_f1),
        "per_class": {
            class_names[i]: {"precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                              "f1": float(per_class_f1[i]), "support": int(per_class_support[i])}
            for i in range(len(class_ids))
        },
        "confusion_matrix": cm.tolist(), "confusion_matrix_class_order": class_names,
        "full_scene_predicted_percent": full_scene_pct,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    # --- Step 6: compare ---
    print("\n" + "=" * 70 + "\nCOMPARISON: Baseline (Experiment B) vs Model 1.1\n" + "=" * 70)
    print(f"{'Metric':20s} {'Baseline':>10s} {'Model 1.1':>10s} {'Delta':>10s}")
    for metric in ["accuracy", "macro_f1", "weighted_f1"]:
        b, v = baseline[metric], v1_1_result[metric]
        print(f"{metric:20s} {b:10.4f} {v:10.4f} {v-b:+10.4f}")
    print("\nPer-class F1:")
    print(f"{'Class':14s} {'Baseline':>10s} {'Model 1.1':>10s} {'Delta':>10s}")
    for cn in class_names:
        b = baseline["per_class"][cn]["f1"]
        v = v1_1_result["per_class"][cn]["f1"]
        print(f"{cn:14s} {b:10.4f} {v:10.4f} {v-b:+10.4f}")
    print("\nFull-scene predicted %:")
    print(f"{'Class':14s} {'Baseline':>10s} {'Model 1.1':>10s} {'Reference':>10s}")
    ref_pct = baseline_meta["reference_label_prevalence_percent"]
    for cn in class_names:
        print(f"{cn:14s} {baseline['full_scene_predicted_percent'][cn]:10.2f} "
              f"{v1_1_result['full_scene_predicted_percent'][cn]:10.2f} {ref_pct[cn]:10.2f}")

    comparison = {"baseline_experiment_B": baseline, "model_1_1": v1_1_result,
                  "reference_label_prevalence_percent": ref_pct}
    with open(f"{OUT_DIR}/comparison_report.json", "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nWrote {OUT_DIR}/comparison_report.json")

    # --- Save model separately, generate full artifact set under model1_v1_1/ ---
    joblib.dump(model, MODEL_PATH)
    print(f"Saved Model 1.1 to {MODEL_PATH} (does NOT overwrite {cfg['paths']['model_path']})")

    print("\nGenerating Model 1.1 prediction + confidence rasters...")
    pred_raster, conf_raster = predict_full_raster(model, feature_array, valid_mask,
                                                     cfg["nodata_value"], return_confidence=True)
    write_prediction_geotiff(pred_raster, transform, crs, f"{OUT_DIR}/lulc_prediction_v1_1.tif", cfg["nodata_value"])
    write_confidence_geotiff(conf_raster, transform, crs, f"{OUT_DIR}/lulc_confidence_v1_1.tif")
    conf_stats = summarize_confidence(conf_raster, valid_mask)
    print("Confidence stats:", conf_stats)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(class_names))); ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right"); ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix - Model 1.1 (hybrid sqrt sampling)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/confusion_matrix_v1_1.png", dpi=150)
    print(f"Saved {OUT_DIR}/confusion_matrix_v1_1.png")

    print(f"\nTotal Model 1.1 run time: {time.time()-t0:.1f}s")
    print(f"\nProduction Model 1 (Experiment B) files UNTOUCHED: "
          f"{cfg['paths']['model_path']}, {cfg['paths']['prediction_tif']}, outputs/metadata.json")


if __name__ == "__main__":
    main()
