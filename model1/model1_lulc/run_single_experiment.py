"""
Run ONE experiment (A, B, or C) using the cached shared inputs from
cache_shared_inputs.py, and append its result to
outputs/experiment_comparison.json. Designed to run as an independent,
short-lived process per experiment so a single long synchronous call
isn't required.

Usage: python run_single_experiment.py A
       python run_single_experiment.py B
       python run_single_experiment.py C
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

from src.config import load_config, ensure_dirs
from src.sampling import stratified_sample, finalize_columns, spatial_block_split
from src.train import train_model

CACHE_PATH = "data/processed/features/shared_inputs_cache.pkl"
RESULTS_PATH = "outputs/experiment_comparison.json"

EXPERIMENTS = {
    "A": ("A_baseline_balanced", "equal_count", "balanced"),
    "B": ("B_equal_count_unweighted", "equal_count", None),
    "C": ("C_natural_prior_unweighted", "natural_prior", None),
}


def main(key: str):
    name, mode, cw = EXPERIMENTS[key]
    cfg = load_config()
    ensure_dirs(cfg)

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    feature_array = cache["feature_array"]
    valid_mask = cache["valid_mask"]
    aligned_labels = cache["aligned_labels"]
    transform = cache["transform"]

    print(f"\n{'='*70}\nEXPERIMENT {name}: mode={mode}, class_weight={cw}\n{'='*70}")
    t0 = time.time()

    df = stratified_sample(
        feature_array, aligned_labels, transform,
        samples_per_class=cfg["sampling"]["samples_per_class"],
        target_classes=cfg["target_classes"],
        random_state=42, mode=mode, max_total_samples=20000,
    )
    df = finalize_columns(df, cfg["features"]["names"])
    df = spatial_block_split(df, cfg["sampling"]["spatial_block_size_m"],
                              cfg["sampling"]["test_block_fraction"], 42)

    model, (X_train, y_train), (X_test, y_test) = train_model(cfg, df, class_weight=cw, random_state=42)
    print(f"  Training done at {time.time()-t0:.1f}s")

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
    print(f"  Test eval done at {time.time()-t0:.1f}s: acc={accuracy:.3f} macro_f1={macro_f1:.3f}")

    # Full-scene prediction proportions (in chunks to bound peak memory).
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
    print(f"  Full-scene prediction done at {time.time()-t0:.1f}s: {full_scene_pct}")

    elapsed = time.time() - t0
    result = {
        "experiment": name, "sampling_mode": mode, "class_weight": cw,
        "n_train_samples": int(len(X_train)), "n_test_samples": int(len(X_test)),
        "accuracy": float(accuracy), "macro_f1": float(macro_f1), "weighted_f1": float(weighted_f1),
        "per_class": {
            class_names[i]: {"precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                              "f1": float(per_class_f1[i]), "support": int(per_class_support[i])}
            for i in range(len(class_ids))
        },
        "confusion_matrix": cm.tolist(), "confusion_matrix_class_order": class_names,
        "full_scene_predicted_percent": full_scene_pct, "elapsed_seconds": round(elapsed, 1),
    }

    os.makedirs("outputs", exist_ok=True)
    os.makedirs(f"models/experiments", exist_ok=True)
    joblib.dump(model, f"models/experiments/{name}.joblib")
    df.to_csv(f"outputs/training_data_{name}.csv", index=False)

    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as f:
            all_results = json.load(f)
    else:
        ref_counts = {c: int((aligned_labels == c).sum()) for c in class_ids}
        ref_total = sum(ref_counts.values())
        ref_pct = {cfg["target_classes"][c]: round(100 * ref_counts[c] / ref_total, 2) for c in class_ids}
        all_results = {
            "reference_label_prevalence_percent": ref_pct,
            "note": ("reference_label_prevalence is WorldCover-derived reference-label "
                     "prevalence within the valid Sentinel-2 area, not field-verified ground "
                     "truth — the closest available prior, not a target to force predictions toward."),
            "experiments": [],
        }
    all_results["experiments"] = [r for r in all_results["experiments"] if r["experiment"] != name]
    all_results["experiments"].append(result)
    with open(RESULTS_PATH, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nExperiment {name} complete in {elapsed:.1f}s. Saved model + result.")


if __name__ == "__main__":
    main(sys.argv[1])
